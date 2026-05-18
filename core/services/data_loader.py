import pandas as pd
from django.db import connection


def query_to_df(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


# ── SLAUGHTER ──────────────────────────────────────────────────────────────────

def get_slaughter_all():
    return query_to_df("""
        SELECT slaughter_date, monday_of_week, commodity, class_name, period,
               slaughter, week_ago, year_ago, week_to_date, current_year_to_date,
               previous_year_to_date, pct_change, week_of_year, year, volume, source
        FROM slaughter
        WHERE source = 'harvest3'
        ORDER BY slaughter_date ASC
    """)


def get_carcass_weights():
    return query_to_df("""
        SELECT report_date, for_date_begin, purchase_type,
               avg_carcass_weight, avg_net_price, head_count, year, index_by_year
        FROM carcass_weights
        WHERE avg_carcass_weight IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_cow_harvest():
    return query_to_df("""
        SELECT report_date, class_name, volume, unit, year, index_by_year
        FROM cow_harvest
        WHERE class_name IN ('Dairy Cows', 'Other Cows')
          AND volume IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_slaughter_summary():
    return query_to_df("""
        SELECT slaughter, year_ago, week_ago, slaughter_date, commodity
        FROM slaughter
        WHERE source = 'harvest3' AND commodity IN ('Cattle', 'Hogs')
          AND period = 'Current'
        ORDER BY slaughter_date DESC
        LIMIT 20
    """)


# ── CUTOUT ─────────────────────────────────────────────────────────────────────

def get_cutout_all():
    return query_to_df("""
        SELECT report_date, attribute, value, trend, week_of_year, year, index_by_year
        FROM cutout_values
        WHERE value IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_cattle_primals():
    return query_to_df("""
        SELECT report_date, primal_desc, choice_600_900, select_600_900,
               week_of_year, year, start_of_week, end_of_week
        FROM cattle_primal
        WHERE choice_600_900 IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_pork_primals():
    return query_to_df("""
        SELECT report_date, commodity, value, week_of_year, year,
               start_of_week, end_of_week
        FROM pork_primals
        WHERE value IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_cutout_summary():
    return query_to_df("""
        SELECT attribute, value, report_date
        FROM cutout_values
        WHERE value IS NOT NULL
        ORDER BY report_date DESC
        LIMIT 14
    """)


# ── CASH vs FUTURES ────────────────────────────────────────────────────────────

def get_cash_cattle_all():
    return query_to_df("""
        SELECT report_date, class_description, selling_basis,
               grade_description, weighted_avg_price, year, index_by_year
        FROM cash_cattle
        WHERE weighted_avg_price IS NOT NULL
          AND weighted_avg_price BETWEEN 80 AND 400
        ORDER BY report_date ASC
    """)


def get_futures_endpoint_all():
    return query_to_df("""
        SELECT trading_day, commodity, month, year, close,
               commodity_month, symbol
        FROM futures_endpoint
        WHERE close IS NOT NULL AND commodity IN ('LE', 'HE')
        ORDER BY trading_day ASC
    """)


def get_basis_summary():
    cash = query_to_df("""
        SELECT report_date, weighted_avg_price
        FROM cash_cattle
        WHERE class_description = 'ALL BEEF TYPE'
          AND weighted_avg_price BETWEEN 80 AND 400
        ORDER BY report_date DESC LIMIT 30
    """)
    futures = query_to_df("""
        SELECT trading_day, close
        FROM futures_endpoint
        WHERE commodity = 'LE' AND close IS NOT NULL
        ORDER BY trading_day DESC LIMIT 30
    """)
    return cash, futures


# ── LRP ────────────────────────────────────────────────────────────────────────

def get_lrp_all():
    return query_to_df("""
        SELECT commodity, coverage_level_percent, coverage_price, end_date,
               endorsement_length, expected_ending_value, head_count,
               livestock_rate, per_head_premium, per_cwt_premium,
               producer_premium, subsidy_percent, target_weight,
               futures_price, cme_premium, strike, grouping_date,
               weekdays_to_expiration, expiration_date, sales_effective_date
        FROM lrp_quotes
        ORDER BY commodity, coverage_level_percent, endorsement_length
    """)


def get_lrp_summary():
    return query_to_df("""
        SELECT commodity, coverage_level_percent, coverage_price,
               per_head_premium, futures_price, endorsement_length, subsidy_percent
        FROM lrp_quotes
        ORDER BY coverage_level_percent DESC
        LIMIT 20
    """)


# ── WASDE ──────────────────────────────────────────────────────────────────────

def get_wasde_all():
    return query_to_df("""
        SELECT wasde_number, report_date, report_title, attribute,
               commodity, region, market_year, proj_est_flag, value,
               unit, release_date, forecast_year, forecast_month,
               market_date, is_latest_two_dates
        FROM wasde_reports
        WHERE value IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_wasde_summary():
    return query_to_df("""
        SELECT commodity, attribute, value, report_date, market_year
        FROM wasde_reports
        WHERE commodity IN ('Steers', 'Beef', 'Barrows and gilts', 'Pork')
          AND value IS NOT NULL
        ORDER BY report_date DESC
        LIMIT 30
    """)


# ── DASHBOARD SPECIFIC ─────────────────────────────────────────────────────────

def get_dashboard_kpis():
    """All KPI data for dashboard cards — latest week vs previous week."""
    return query_to_df("""
        WITH ranked AS (
            SELECT slaughter_date, commodity, slaughter, week_ago,
                   ROW_NUMBER() OVER (PARTITION BY commodity ORDER BY slaughter_date DESC) as rn
            FROM slaughter
            WHERE source = 'harvest3' AND period = 'Current'
              AND commodity IN ('Cattle', 'Hogs') AND slaughter > 1000
        )
        SELECT slaughter_date, commodity, slaughter, week_ago
        FROM ranked WHERE rn = 1
    """)


def get_dashboard_cutout_kpi():
    """Latest Choice and Select cutout for KPI cards."""
    return query_to_df("""
        WITH ranked AS (
            SELECT report_date, attribute, value,
                   ROW_NUMBER() OVER (PARTITION BY attribute ORDER BY report_date DESC) as rn
            FROM cutout_values
            WHERE attribute IN ('Choice', 'Select') AND value IS NOT NULL
        )
        SELECT report_date, attribute, value FROM ranked WHERE rn <= 7
        ORDER BY attribute, report_date DESC
    """)


def get_dashboard_cash_kpi():
    """Latest cash cattle price for KPI card."""
    return query_to_df("""
        SELECT report_date, weighted_avg_price
        FROM cash_cattle
        WHERE class_description = 'ALL BEEF TYPE'
          AND selling_basis = 'LIVE DELIVERED'
          AND weighted_avg_price BETWEEN 100 AND 400
        ORDER BY report_date DESC
        LIMIT 14
    """)