from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import SalesHistory, Product, Location
from app.schemas.planning import (
    ForecastItem,
    ForecastResponse,
    ForecastEvaluationPoint,
    ForecastEvaluationSeries,
    ForecastEvaluationResponse,
)



def compute_demand_forecast(
    db: Session,
    horizon_days: int = 7,
    sku_id: Optional[str] = None,
    destination_id: Optional[str] = None,
) -> ForecastResponse:
    """
    Computes demand forecasts by SKU and destination using historical sales observations.
    - Moving average (7-day rolling window) and seasonal-naive baselines.
    - Strict temporal boundary: Never uses future observations to predict past periods.
    - Holdout evaluation: Computes chronological out-of-sample MAE and WAPE on holdout period.
    - Handles missing data and zero demand explicitly.
    - Forecasts are kept strictly separate from actual sales and inventory records.
    """
    # 1. Fetch sales observations chronologically
    query = db.query(SalesHistory).order_by(SalesHistory.sales_date.asc())
    if sku_id:
        query = query.filter(SalesHistory.sku_id == sku_id.strip())
    if destination_id:
        query = query.filter(SalesHistory.destination_id == destination_id.strip())

    sales_records = query.all()

    # Pre-fetch products and locations for descriptive names
    products = {p.sku_id: p.name for p in db.query(Product).all()}
    destinations = {l.location_id: l.name for l in db.query(Location).all()}

    # Group sales chronologically: (sku_id, destination_id) -> list of (date, qty)
    history_by_series: Dict[Tuple[str, str], List[Tuple[datetime, float]]] = defaultdict(list)
    for s in sales_records:
        history_by_series[(s.sku_id, s.destination_id)].append((s.sales_date, float(s.quantity)))

    # Also identify all valid destination locations and products from DB
    destination_types = {"retail_destination", "distributor_warehouse", "regional_warehouse", "company_warehouse", "cnf_facility"}
    sales_destinations = {s.destination_id for s in sales_records}
    all_locations = db.query(Location).all()
    target_locations = [
        l.location_id for l in all_locations
        if l.location_type in destination_types or l.location_id in sales_destinations
    ]
    all_sku_ids = list(products.keys())

    forecast_items: List[ForecastItem] = []
    total_holdout_errors: List[float] = []
    total_holdout_actuals: List[float] = []

    # Evaluate all pairs that have sales or are active target nodes
    series_keys = set(history_by_series.keys())
    for d_id in target_locations:
        for s_id in all_sku_ids:
            series_keys.add((s_id, d_id))

    for (s_id, d_id) in sorted(series_keys):
        records = history_by_series.get((s_id, d_id), [])
        prod_name = products.get(s_id, s_id)
        dest_name = destinations.get(d_id, d_id)

        # Case 1: No sales data at all
        if not records:
            forecast_items.append(
                ForecastItem(
                    sku_id=s_id,
                    product_name=prod_name,
                    destination_id=d_id,
                    destination_name=dest_name,
                    horizon_days=horizon_days,
                    daily_forecast_rate=0.0,
                    total_forecast_demand=0.0,
                    forecast_method="zero_baseline",
                    data_sufficiency="insufficient_history",
                    mae=None,
                    wape=None,
                    assumptions="No historical sales observations recorded for this SKU-destination corridor.",
                )
            )
            continue

        quantities = [qty for (_, qty) in records]
        n_obs = len(quantities)
        total_vol = sum(quantities)

        # Case 2: Zero demand across all observations
        if total_vol == 0:
            forecast_items.append(
                ForecastItem(
                    sku_id=s_id,
                    product_name=prod_name,
                    destination_id=d_id,
                    destination_name=dest_name,
                    horizon_days=horizon_days,
                    daily_forecast_rate=0.0,
                    total_forecast_demand=0.0,
                    forecast_method="zero_baseline",
                    data_sufficiency="zero_demand",
                    mae=0.0,
                    wape=0.0,
                    assumptions=f"All {n_obs} historical sales points recorded zero quantity.",
                )
            )
            continue

        # Case 3: Sparse history (< 7 observations)
        if n_obs < 7:
            daily_avg = total_vol / max(1, n_obs)
            forecast_items.append(
                ForecastItem(
                    sku_id=s_id,
                    product_name=prod_name,
                    destination_id=d_id,
                    destination_name=dest_name,
                    horizon_days=horizon_days,
                    daily_forecast_rate=round(daily_avg, 2),
                    total_forecast_demand=round(daily_avg * horizon_days, 1),
                    forecast_method="sparse_mean",
                    data_sufficiency="insufficient_history",
                    mae=None,
                    wape=None,
                    assumptions=f"Limited sample size ({n_obs} days < 7-day minimum threshold). Baseline simple mean applied.",
                )
            )
            continue

        # Case 4: Sufficient history (>= 7 observations)
        # Chronological holdout evaluation:
        # Train on earlier records, evaluate on last min(7, n_obs // 2) points
        holdout_len = min(7, n_obs // 2)
        train_records = records[:-holdout_len]
        test_records = records[-holdout_len:]

        train_quantities = [q for (_, q) in train_records]
        test_quantities = [q for (_, q) in test_records]

        train_start = train_records[0][0].strftime("%Y-%m-%d") if train_records else "N/A"
        train_end = train_records[-1][0].strftime("%Y-%m-%d") if train_records else "N/A"
        test_start = test_records[0][0].strftime("%Y-%m-%d") if test_records else "N/A"
        test_end = test_records[-1][0].strftime("%Y-%m-%d") if test_records else "N/A"

        training_window = f"{train_start} to {train_end}"
        evaluation_window = f"{test_start} to {test_end}"

        # Method 1: Moving average (7-day window on training set)
        train_window = train_quantities[-7:] if len(train_quantities) >= 7 else train_quantities
        predicted_ma_rate = sum(train_window) / len(train_window)
        ma_errors = [abs(actual - predicted_ma_rate) for actual in test_quantities]
        ma_mae = sum(ma_errors) / len(ma_errors)
        test_actual_sum = sum(test_quantities)
        ma_wape = (sum(ma_errors) / test_actual_sum) if test_actual_sum > 0 else 0.0

        # Method 2: Seasonal-naive (day-of-week 7-day lag if >= 14 observations available)
        selected_method = "moving_average_7d"
        selected_rate = sum(quantities[-7:]) / len(quantities[-7:])
        selected_mae = ma_mae
        selected_wape = ma_wape
        selected_errors = ma_errors

        if len(train_quantities) >= 7 and len(test_quantities) <= 7:
            # Predict each test day from corresponding day 7 days prior in training set
            sn_preds = train_quantities[-len(test_quantities):]
            sn_errors = [abs(actual - pred) for actual, pred in zip(test_quantities, sn_preds)]
            sn_mae = sum(sn_errors) / len(sn_errors)
            sn_wape = (sum(sn_errors) / test_actual_sum) if test_actual_sum > 0 else 0.0

            if sn_wape < ma_wape and sn_mae < ma_mae:
                selected_method = "seasonal_naive_7d"
                # Use mean of the last 7 daily cyclical points
                selected_rate = sum(quantities[-7:]) / 7.0
                selected_mae = sn_mae
                selected_wape = sn_wape
                selected_errors = sn_errors

        total_holdout_errors.extend(selected_errors)
        total_holdout_actuals.extend(test_quantities)

        total_demand = round(selected_rate * horizon_days, 1)

        forecast_items.append(
            ForecastItem(
                sku_id=s_id,
                product_name=prod_name,
                destination_id=d_id,
                destination_name=dest_name,
                horizon_days=horizon_days,
                daily_forecast_rate=round(selected_rate, 2),
                total_forecast_demand=total_demand,
                forecast_method=selected_method,
                data_sufficiency="sufficient",
                mae=round(selected_mae, 2),
                wape=round(selected_wape * 100.0, 1),
                training_window=training_window,
                evaluation_window=evaluation_window,
                assumptions=(
                    f"Out-of-sample holdout evaluation over {training_window} (train) and {evaluation_window} (eval). "
                    f"Selected {selected_method}: MAE={selected_mae:.2f}, WAPE={selected_wape * 100:.1f}%."
                ),
            )
        )

    # Compute overall holdout summary
    holdout_summary = None
    if total_holdout_actuals:
        overall_mae = sum(total_holdout_errors) / len(total_holdout_errors)
        total_act = sum(total_holdout_actuals)
        overall_wape = (sum(total_holdout_errors) / total_act * 100.0) if total_act > 0 else 0.0
        holdout_summary = (
            f"Evaluated on {len(total_holdout_actuals)} holdout observations across {len(forecast_items)} series. "
            f"Overall Out-of-Sample MAE: {overall_mae:.2f} cases, Overall WAPE: {overall_wape:.1f}%."
        )

    return ForecastResponse(
        horizon_days=horizon_days,
        total_skus=len(all_sku_ids),
        total_destinations=len(target_locations),
        forecasts=forecast_items,
        holdout_evaluation_summary=holdout_summary,
    )


def compute_forecast_evaluation(
    db: Session,
    horizon_days: int = 7,
    sku_id: Optional[str] = None,
    destination_id: Optional[str] = None,
) -> ForecastEvaluationResponse:
    """
    Computes ML model evaluation comparing actual historical demand against predicted demand
    using matched SKU, location, and date records from out-of-sample holdout evaluation.
    - MAE = mean absolute error = sum(|actual - predicted|) / sample_count
    - WAPE = sum(|actual - predicted|) / sum(actual) * 100
    - Forecast accuracy = 100 - WAPE
    - Strict chronological holdout without future data leakage.
    - Generates aligned time-series with clear separation between historical holdout and future forecast.
    """
    now = datetime.now(timezone.utc)

    # 1. Fetch sales observations chronologically
    query = db.query(SalesHistory).order_by(SalesHistory.sales_date.asc())
    if sku_id and sku_id.strip() != "all":
        query = query.filter(SalesHistory.sku_id == sku_id.strip())
    if destination_id and destination_id.strip() != "all":
        query = query.filter(SalesHistory.destination_id == destination_id.strip())

    sales_records = query.all()
    products = {p.sku_id: p.name for p in db.query(Product).all()}
    destinations = {l.location_id: l.name for l in db.query(Location).all()}

    history_by_series: Dict[Tuple[str, str], List[Tuple[Any, float]]] = defaultdict(list)
    for s in sales_records:
        history_by_series[(s.sku_id, s.destination_id)].append((s.sales_date, float(s.quantity)))

    series_list: List[ForecastEvaluationSeries] = []
    all_holdout_errors: List[float] = []
    all_holdout_actuals: List[float] = []
    all_holdout_preds: List[float] = []
    date_aligned_points: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"actual": 0.0, "predicted": 0.0, "has_actual": False, "is_holdout": False, "is_future": False}
    )

    min_eval_date = None
    max_eval_date = None

    for (s_id, d_id), records in sorted(history_by_series.items()):
        prod_name = products.get(s_id, s_id)
        dest_name = destinations.get(d_id, d_id)
        quantities = [qty for (_, qty) in records]
        n_obs = len(quantities)
        total_vol = sum(quantities)

        if not records or n_obs < 7:
            # Insufficient history for safe holdout evaluation (< 7 observations)
            daily_avg = total_vol / max(1, n_obs)
            series_points: List[ForecastEvaluationPoint] = []

            # Include historical actuals as baseline without holdout prediction
            for rec_date, actual_val in records:
                d_str = rec_date.strftime("%Y-%m-%d") if hasattr(rec_date, "strftime") else str(rec_date)
                series_points.append(
                    ForecastEvaluationPoint(
                        date=d_str,
                        sku_id=s_id,
                        destination_id=d_id,
                        actual_demand=round(actual_val, 1),
                        predicted_demand=round(daily_avg, 1),
                        error=None,
                        is_holdout=False,
                        is_future=False,
                    )
                )

            # Future points only for horizon
            last_date = records[-1][0] if records else (now - timedelta(days=1)).date()
            if hasattr(last_date, "date"):
                last_date = last_date.date()
            elif isinstance(last_date, str):
                last_date = datetime.strptime(last_date[:10], "%Y-%m-%d").date()

            for i in range(1, horizon_days + 1):
                f_date = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
                pt = ForecastEvaluationPoint(
                    date=f_date,
                    sku_id=s_id,
                    destination_id=d_id,
                    actual_demand=None,
                    predicted_demand=round(daily_avg, 1),
                    error=None,
                    is_holdout=False,
                    is_future=True,
                )
                series_points.append(pt)
                dp = date_aligned_points[f_date]
                dp["predicted"] += round(daily_avg, 1)
                dp["is_future"] = True

            series_list.append(
                ForecastEvaluationSeries(
                    sku_id=s_id,
                    product_name=prod_name,
                    destination_id=d_id,
                    destination_name=dest_name,
                    forecast_method="sparse_mean",
                    data_sufficiency="insufficient_history",
                    sample_count=n_obs,
                    total_actual_demand=round(total_vol, 1) if n_obs > 0 else None,
                    total_predicted_demand=None,
                    mae=None,
                    wape=None,
                    accuracy_percent=None,
                    evaluation_period=None,
                    evaluated_at=now,
                    points=series_points,
                )
            )
            continue

        # Case: Sufficient observations (>= 7)
        holdout_len = min(7, n_obs // 2)
        train_records = records[:-holdout_len]
        test_records = records[-holdout_len:]

        train_quantities = [q for (_, q) in train_records]
        test_quantities = [q for (_, q) in test_records]

        # 1. 7-day Moving average on training
        train_window = train_quantities[-7:] if len(train_quantities) >= 7 else train_quantities
        ma_rate = sum(train_window) / len(train_window)
        ma_errors = [abs(act - ma_rate) for act in test_quantities]
        ma_mae = sum(ma_errors) / len(ma_errors)
        test_act_sum = sum(test_quantities)
        ma_wape = (sum(ma_errors) / test_act_sum * 100.0) if test_act_sum > 0 else 0.0

        # 2. Seasonal naive check
        chosen_method = "moving_average_7d"
        chosen_preds = [ma_rate] * len(test_quantities)
        chosen_errors = ma_errors
        chosen_mae = ma_mae
        chosen_wape = ma_wape
        daily_future_rate = sum(quantities[-7:]) / len(quantities[-7:])

        if len(train_quantities) >= 7 and len(test_quantities) <= 7:
            sn_preds = train_quantities[-len(test_quantities):]
            sn_errors = [abs(act - pred) for act, pred in zip(test_quantities, sn_preds)]
            sn_mae = sum(sn_errors) / len(sn_errors)
            sn_wape = (sum(sn_errors) / test_act_sum * 100.0) if test_act_sum > 0 else 0.0

            if sn_wape < ma_wape and sn_mae < ma_mae:
                chosen_method = "seasonal_naive_7d"
                chosen_preds = sn_preds
                chosen_errors = sn_errors
                chosen_mae = sn_mae
                chosen_wape = sn_wape
                daily_future_rate = sum(quantities[-7:]) / 7.0

        all_holdout_errors.extend(chosen_errors)
        all_holdout_actuals.extend(test_quantities)
        all_holdout_preds.extend(chosen_preds)

        t_start = test_records[0][0]
        t_end = test_records[-1][0]
        if hasattr(t_start, "date"):
            t_start = t_start.date()
        if hasattr(t_end, "date"):
            t_end = t_end.date()

        if min_eval_date is None or t_start < min_eval_date:
            min_eval_date = t_start
        if max_eval_date is None or t_end > max_eval_date:
            max_eval_date = t_end

        series_points: List[ForecastEvaluationPoint] = []
        for (rec_date, actual_val), pred_val, err_val in zip(test_records, chosen_preds, chosen_errors):
            d_str = rec_date.strftime("%Y-%m-%d") if hasattr(rec_date, "strftime") else str(rec_date)
            pt = ForecastEvaluationPoint(
                date=d_str,
                sku_id=s_id,
                destination_id=d_id,
                actual_demand=round(actual_val, 1),
                predicted_demand=round(pred_val, 1),
                error=round(err_val, 1),
                is_holdout=True,
                is_future=False,
            )
            series_points.append(pt)
            dp = date_aligned_points[d_str]
            dp["actual"] += actual_val
            dp["predicted"] += pred_val
            dp["has_actual"] = True
            dp["is_holdout"] = True

        # Future forecast points
        last_dt = records[-1][0]
        if hasattr(last_dt, "date"):
            last_dt = last_dt.date()
        elif isinstance(last_dt, str):
            last_dt = datetime.strptime(last_dt[:10], "%Y-%m-%d").date()

        for i in range(1, horizon_days + 1):
            f_date = (last_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            pt = ForecastEvaluationPoint(
                date=f_date,
                sku_id=s_id,
                destination_id=d_id,
                actual_demand=None,
                predicted_demand=round(daily_future_rate, 1),
                error=None,
                is_holdout=False,
                is_future=True,
            )
            series_points.append(pt)
            dp = date_aligned_points[f_date]
            dp["predicted"] += round(daily_future_rate, 1)
            dp["is_future"] = True

        eval_period_str = f"{t_start} to {t_end}"
        series_acc = max(0.0, round(100.0 - chosen_wape, 1))

        series_list.append(
            ForecastEvaluationSeries(
                sku_id=s_id,
                product_name=prod_name,
                destination_id=d_id,
                destination_name=dest_name,
                forecast_method=chosen_method,
                data_sufficiency="sufficient",
                sample_count=len(test_records),
                total_actual_demand=round(sum(test_quantities), 1),
                total_predicted_demand=round(sum(chosen_preds), 1),
                mae=round(chosen_mae, 2),
                wape=round(chosen_wape, 1),
                accuracy_percent=series_acc,
                evaluation_period=eval_period_str,
                evaluated_at=now,
                points=series_points,
            )
        )

    # Build aligned timeseries across all matched series
    aligned_list: List[ForecastEvaluationPoint] = []
    for d_str in sorted(date_aligned_points.keys()):
        data = date_aligned_points[d_str]
        act = round(data["actual"], 1) if data["has_actual"] else None
        pred = round(data["predicted"], 1)
        err = round(abs(act - pred), 1) if act is not None else None
        aligned_list.append(
            ForecastEvaluationPoint(
                date=d_str,
                sku_id=sku_id or "all",
                destination_id=destination_id or "all",
                actual_demand=act,
                predicted_demand=pred,
                error=err,
                is_holdout=data["is_holdout"],
                is_future=data["is_future"],
            )
        )

    # Overall Metrics
    total_sample_count = len(all_holdout_errors)
    overall_actual = sum(all_holdout_actuals) if all_holdout_actuals else None
    overall_pred = sum(all_holdout_preds) if all_holdout_preds else None
    overall_mae = (sum(all_holdout_errors) / total_sample_count) if total_sample_count > 0 else None
    overall_wape = (sum(all_holdout_errors) / overall_actual * 100.0) if (overall_actual and overall_actual > 0) else None
    overall_accuracy = max(0.0, round(100.0 - overall_wape, 1)) if overall_wape is not None else None
    overall_period = f"{min_eval_date} to {max_eval_date}" if (min_eval_date and max_eval_date) else None
    overall_sufficiency = "sufficient" if total_sample_count >= 7 else ("zero_demand" if (overall_actual == 0) else "insufficient_history")

    return ForecastEvaluationResponse(
        evaluated_at=now,
        horizon_days=horizon_days,
        sample_count=total_sample_count,
        total_actual_demand=round(overall_actual, 1) if overall_actual is not None else None,
        total_predicted_demand=round(overall_pred, 1) if overall_pred is not None else None,
        mae=round(overall_mae, 2) if overall_mae is not None else None,
        wape=round(overall_wape, 1) if overall_wape is not None else None,
        accuracy_percent=overall_accuracy,
        evaluation_period=overall_period,
        data_sufficiency=overall_sufficiency,
        model_name="Baseline Statistical Forecast (7-day Rolling Moving Average / Seasonal Naive)",
        accuracy_formula_note="Forecast accuracy is defined as 100 - WAPE (%). Clamped to 0.0% when WAPE exceeds 100%.",
        series=series_list,
        aligned_timeseries=aligned_list,
    )

