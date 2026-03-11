import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

DATA_PATH = Path('Exportaciones País.csv')

SP_MONTHS = {
    'Ene': 1, 'Feb': 2, 'Mar': 3, 'Abr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Ago': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dic': 12
}


def load_series(col_name):
    df = pd.read_csv(DATA_PATH, encoding='utf-8')
    # drop fully empty trailing columns
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df = df.rename(columns={c: c.strip() for c in df.columns})
    # parse Fecha like 'Ene 2010'
    fecha = df['Fecha'].astype(str).str.strip()
    months = fecha.str.split().str[0]
    years = fecha.str.split().str[1].astype(int)
    month_nums = months.map(SP_MONTHS)
    dates = pd.to_datetime(dict(year=years, month=month_nums, day=1))
    s = df[col_name].astype(str).str.replace('"','').str.replace(',','')
    s = pd.to_numeric(s, errors='coerce')
    series = pd.Series(s.values, index=dates)
    series.index = pd.DatetimeIndex(series.index).to_period('M').to_timestamp()
    series = series.asfreq('MS')
    series.name = col_name
    return series


def fit_with_pmdarima(train):
    try:
        import pmdarima as pm
    except Exception:
        return None
    m = pm.auto_arima(train, seasonal=True, m=12, trace=False,
                      error_action='ignore', suppress_warnings=True,
                      stepwise=True)
    return m


def fit_sarimax_grid(train, max_p=2, max_d=1, max_q=2, max_P=1, max_D=1, max_Q=1):
    import itertools
    import statsmodels.api as sm
    best_aic = np.inf
    best_order = None
    best_seasonal = None
    best_model = None
    for p, d, q in itertools.product(range(max_p+1), range(max_d+1), range(max_q+1)):
        for P, D, Q in itertools.product(range(max_P+1), range(max_D+1), range(max_Q+1)):
            try:
                mod = sm.tsa.statespace.SARIMAX(train,
                                                order=(p,d,q),
                                                seasonal_order=(P,D,Q,12),
                                                enforce_stationarity=False,
                                                enforce_invertibility=False)
                res = mod.fit(disp=False)
                if res.aic < best_aic:
                    best_aic = res.aic
                    best_order = (p,d,q)
                    best_seasonal = (P,D,Q,12)
                    best_model = res
            except Exception:
                continue
    return best_model, best_order, best_seasonal


def forecast_and_plot(series, name, out_png, out_csv):
    from sklearn.metrics import mean_squared_error
    import math
    import statsmodels.api as sm

    # hold out last 12 months for validation
    if len(series) < 36:
        raise ValueError('Series too short')
    train = series[:-12]
    test = series[-12:]

    model_obj = fit_with_pmdarima(train)
    pmd_used = False
    if model_obj is not None:
        pmd_used = True
        # pmdarima wrapper has predict and predict(n_periods)
        preds_test, conf_test = model_obj.predict(n_periods=12, return_conf_int=True)
        preds_test = pd.Series(preds_test, index=test.index)
        conf_test = pd.DataFrame(conf_test, index=test.index, columns=['lower','upper'])
        order_text = str(model_obj.order) + ' seasonal ' + str(model_obj.seasonal_order)
    else:
        res, order, seasonal = fit_sarimax_grid(train)
        preds_test = res.get_forecast(steps=12)
        preds_test_mean = pd.Series(preds_test.predicted_mean.values, index=test.index)
        conf_test = preds_test.conf_int()
        preds_test = preds_test_mean
        order_text = f'order={order} seasonal={seasonal}'
        res_full = res

    rmse = math.sqrt(mean_squared_error(test.values, preds_test.values))
    mape = np.mean(np.abs((test.values - preds_test.values) / test.values)) * 100

    # Refit on full series for final forecast to Dec 2027
    last_date = series.index.max()
    final_target = pd.Timestamp(year=2027, month=12, day=1)
    months_ahead = (final_target.year - last_date.year) * 12 + (final_target.month - last_date.month)
    if months_ahead <= 0:
        raise ValueError('Series already reaches target')

    if pmd_used:
        model_obj.update(series.values)
        fc_vals, fc_conf = model_obj.predict(n_periods=months_ahead, return_conf_int=True)
        idx = pd.date_range(start=last_date + pd.offsets.MonthBegin(1), periods=months_ahead, freq='MS')
        fc = pd.Series(fc_vals, index=idx)
        fc_ci = pd.DataFrame(fc_conf, index=idx, columns=['lower','upper'])
    else:
        # fit SARIMAX on full series using grid search
        res2, order2, seasonal2 = fit_sarimax_grid(series)
        if res2 is None:
            raise RuntimeError('Could not fit SARIMAX')
        preds = res2.get_forecast(steps=months_ahead)
        idx = pd.date_range(start=last_date + pd.offsets.MonthBegin(1), periods=months_ahead, freq='MS')
        fc = pd.Series(preds.predicted_mean.values, index=idx)
        fc_ci = preds.conf_int()

    # Prepare CSV with validation and forecast values
    idx_all = series.index.union(fc.index)
    df_out = pd.DataFrame(index=idx_all)
    df_out.index.name = 'fecha'
    df_out['actual'] = series.reindex(idx_all).values
    # validation predictions (last 12)
    df_out['val_pred'] = pd.Series(preds_test.values, index=test.index).reindex(idx_all).values
    try:
        df_out['val_lower'] = conf_test.iloc[:,0].reindex(idx_all).values
        df_out['val_upper'] = conf_test.iloc[:,1].reindex(idx_all).values
    except Exception:
        df_out['val_lower'] = np.nan
        df_out['val_upper'] = np.nan
    # final forecast
    df_out['fc_pred'] = fc.reindex(idx_all).values
    try:
        df_out['fc_lower'] = fc_ci.iloc[:,0].reindex(idx_all).values
        df_out['fc_upper'] = fc_ci.iloc[:,1].reindex(idx_all).values
    except Exception:
        df_out['fc_lower'] = np.nan
        df_out['fc_upper'] = np.nan
    # save csv
    df_out.to_csv(out_csv, index=True)

    # Plot
    plt.figure(figsize=(12,6))
    plt.plot(series.index, series.values, label='Historical', color='black')
    plt.plot(test.index, preds_test.values, label='Validation forecast (12m)', color='tab:orange')
    plt.fill_between(test.index, conf_test.iloc[:,0], conf_test.iloc[:,1], color='orange', alpha=0.25)
    plt.plot(fc.index, fc.values, label=f'Forecast to 2027 ({months_ahead}m)', color='tab:green')
    plt.fill_between(fc.index, fc_ci.iloc[:,0], fc_ci.iloc[:,1], color='green', alpha=0.2)
    plt.axvline(series.index[-13], color='gray', linestyle='--', linewidth=0.8)
    plt.title(f'{name} — {order_text} | RMSE={rmse:.1f} MAPE={mape:.2f}%')
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()

    # also print summary
    print(f'Wrote {out_png} and {out_csv} — RMSE={rmse:.2f} MAPE={mape:.2f}%')


def main():
    exp = load_series('Exportación')
    imp = load_series('Importación')
    forecast_and_plot(exp, 'Exportaciones (Mexico)', 'forecast_exportaciones.png', 'forecast_exportaciones.csv')
    forecast_and_plot(imp, 'Importaciones (Mexico)', 'forecast_importaciones.png', 'forecast_importaciones.csv')


if __name__ == '__main__':
    main()
