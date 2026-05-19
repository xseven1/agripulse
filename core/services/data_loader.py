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


# ── MODULE KPI QUERIES ─────────────────────────────────────────────────────────

def get_slaughter_kpis():
    """Latest 2 weeks of slaughter for KPI WoW comparison."""
    return query_to_df("""
        WITH weekly AS (
            SELECT commodity,
                   DATE_TRUNC('week', slaughter_date) as week_start,
                   SUM(slaughter) as total
            FROM slaughter
            WHERE source = 'harvest3' AND period = 'Current'
              AND commodity IN ('Cattle', 'Hogs') AND slaughter > 1000
            GROUP BY commodity, DATE_TRUNC('week', slaughter_date)
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY commodity ORDER BY week_start DESC) as rn
            FROM weekly
        )
        SELECT commodity, week_start, total FROM ranked WHERE rn <= 2
        ORDER BY commodity, week_start DESC
    """)


def get_carcass_kpis():
    """Latest 2 carcass weight readings for WoW KPI."""
    return query_to_df("""
        SELECT report_date, avg_carcass_weight
        FROM carcass_weights
        WHERE purchase_type = 'Prod. Sold (All Purchase Types)'
          AND avg_carcass_weight IS NOT NULL
        ORDER BY report_date DESC
        LIMIT 4
    """)


def get_cutout_kpis():
    """Latest cutout values for KPI cards."""
    return query_to_df("""
        WITH ranked AS (
            SELECT attribute, value, report_date,
                   ROW_NUMBER() OVER (PARTITION BY attribute ORDER BY report_date DESC) as rn
            FROM cutout_values
            WHERE attribute IN ('Choice', 'Select') AND value IS NOT NULL
        )
        SELECT attribute, value, report_date FROM ranked WHERE rn <= 3
        ORDER BY attribute, report_date DESC
    """)


def get_primal_kpis():
    """Top gaining and losing primal this week."""
    return query_to_df("""
        WITH latest AS (
            SELECT primal_desc, choice_600_900, report_date,
                   ROW_NUMBER() OVER (PARTITION BY primal_desc ORDER BY report_date DESC) as rn
            FROM cattle_primal WHERE choice_600_900 IS NOT NULL
        ),
        curr AS (SELECT primal_desc, choice_600_900 FROM latest WHERE rn = 1),
        prev AS (SELECT primal_desc, choice_600_900 FROM latest WHERE rn = 2)
        SELECT c.primal_desc,
               c.choice_600_900 as curr_val,
               p.choice_600_900 as prev_val,
               c.choice_600_900 - p.choice_600_900 as delta
        FROM curr c JOIN prev p ON c.primal_desc = p.primal_desc
        ORDER BY delta DESC
    """)


def get_basis_kpis():
    """Latest cash and futures for basis KPI."""
    cash = query_to_df("""
        SELECT report_date, weighted_avg_price
        FROM cash_cattle
        WHERE class_description = 'ALL BEEF TYPE'
          AND selling_basis = 'LIVE DELIVERED'
          AND weighted_avg_price BETWEEN 100 AND 400
        ORDER BY report_date DESC LIMIT 7
    """)
    futures = query_to_df("""
        SELECT trading_day, close
        FROM futures_endpoint
        WHERE commodity = 'LE' AND close IS NOT NULL
        ORDER BY trading_day DESC LIMIT 7
    """)
    return cash, futures


def get_lrp_kpis():
    """Key LRP metrics for KPI cards."""
    return query_to_df("""
        SELECT commodity, coverage_level_percent, coverage_price,
               per_head_premium, futures_price, subsidy_percent
        FROM lrp_quotes
        WHERE commodity = 'LIVE CATTLE'
          AND coverage_level_percent >= 0.95
        ORDER BY coverage_level_percent DESC
        LIMIT 5
    """)


def get_wasde_kpis():
    return query_to_df("""
        SELECT commodity, attribute, value, report_date, market_year
        FROM wasde_reports
        WHERE commodity IN ('Beef', 'Pork')
          AND attribute = 'Production'
          AND value > 20000
        ORDER BY report_date DESC
        LIMIT 20
    """)

# ── COMPARABLE WEEK FINDER ─────────────────────────────────────────────────────

def get_comparable_week_matrix():
    """Build the full weekly matrix for comparable week matching.
    Uses cutout + carcass weights going back to 2004."""
    return query_to_df("""
        WITH choice_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(value) as choice_cutout
            FROM cutout_values
            WHERE attribute = 'Choice' AND value IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        select_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(value) as select_cutout
            FROM cutout_values
            WHERE attribute = 'Select' AND value IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        carcass_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(avg_carcass_weight) as carcass_weight
            FROM carcass_weights
            WHERE purchase_type = 'Prod. Sold (All Purchase Types)'
              AND avg_carcass_weight IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        cash_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(weighted_avg_price) as cash_price
            FROM cash_cattle
            WHERE class_description = 'ALL BEEF TYPE'
              AND selling_basis = 'LIVE DELIVERED'
              AND weighted_avg_price BETWEEN 100 AND 400
            GROUP BY DATE_TRUNC('week', report_date)
        )
        SELECT
            ch.week,
            ch.choice_cutout,
            se.select_cutout,
            ch.choice_cutout - se.select_cutout as spread,
            cw.carcass_weight,
            ca.cash_price,
            EXTRACT(WEEK FROM ch.week)::int as week_of_year,
            EXTRACT(YEAR FROM ch.week)::int as year
        FROM choice_weekly ch
        LEFT JOIN select_weekly se ON ch.week = se.week
        LEFT JOIN carcass_weekly cw ON ch.week = cw.week
        LEFT JOIN cash_weekly ca ON ch.week = ca.week
        WHERE ch.choice_cutout IS NOT NULL
          AND cw.carcass_weight IS NOT NULL
        ORDER BY ch.week ASC
    """)


def get_week_outcome(week_date, weeks_forward=4):
    """Get what happened in the 4 weeks after a given week."""
    return query_to_df("""
        WITH choice_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(value) as choice_cutout
            FROM cutout_values
            WHERE attribute = 'Choice' AND value IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        cash_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(weighted_avg_price) as cash_price
            FROM cash_cattle
            WHERE class_description = 'ALL BEEF TYPE'
              AND selling_basis = 'LIVE DELIVERED'
              AND weighted_avg_price BETWEEN 100 AND 400
            GROUP BY DATE_TRUNC('week', report_date)
        )
        SELECT ch.week, ch.choice_cutout, ca.cash_price
        FROM choice_weekly ch
        LEFT JOIN cash_weekly ca ON ch.week = ca.week
        WHERE ch.week > %s AND ch.week <= %s + INTERVAL '%s weeks'
        ORDER BY ch.week ASC
    """, [week_date, week_date, weeks_forward])


def get_hog_comparable_matrix():
    """Weekly matrix for hog comparable week matching — back to 2013."""
    return query_to_df("""
        WITH pork_carcass AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(value) as pork_carcass
            FROM pork_primals
            WHERE commodity = 'Carcass' AND value > 0
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        pork_belly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(value) as belly_value
            FROM pork_primals
            WHERE commodity = 'Belly' AND value > 0
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        hog_carcass_wt AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(avg_carcass_weight) as hog_carcass_weight
            FROM harvest_usda
            WHERE avg_carcass_weight IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        cash_hog AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(wtd_avg) as cash_hog_price
            FROM nearby_futures
            WHERE name = 'National' AND wtd_avg IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        )
        SELECT
            pc.week,
            pc.pork_carcass,
            pb.belly_value,
            hw.hog_carcass_weight,
            ch.cash_hog_price,
            EXTRACT(WEEK FROM pc.week)::int as week_of_year,
            EXTRACT(YEAR FROM pc.week)::int as year
        FROM pork_carcass pc
        LEFT JOIN pork_belly pb ON pc.week = pb.week
        LEFT JOIN hog_carcass_wt hw ON pc.week = hw.week
        LEFT JOIN cash_hog ch ON pc.week = ch.week
        WHERE pc.pork_carcass IS NOT NULL
          AND hw.hog_carcass_weight IS NOT NULL
        ORDER BY pc.week ASC
    """)


def get_hog_week_outcome(week_date, weeks_forward=4):
    """What happened to hog prices in the 4 weeks after a given week."""
    return query_to_df("""
        WITH pork_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(value) as pork_carcass
            FROM pork_primals
            WHERE commodity = 'Carcass' AND value > 0
            GROUP BY DATE_TRUNC('week', report_date)
        ),
        cash_weekly AS (
            SELECT
                DATE_TRUNC('week', report_date) as week,
                AVG(wtd_avg) as cash_price
            FROM nearby_futures
            WHERE name = 'National' AND wtd_avg IS NOT NULL
            GROUP BY DATE_TRUNC('week', report_date)
        )
        SELECT pw.week, pw.pork_carcass, cw.cash_price
        FROM pork_weekly pw
        LEFT JOIN cash_weekly cw ON pw.week = cw.week
        WHERE pw.week > %s AND pw.week <= %s + INTERVAL '%s weeks'
        ORDER BY pw.week ASC
    """, [week_date, week_date, weeks_forward])


# ── DASHBOARD V2 QUERIES ───────────────────────────────────────────────────────

def get_cattle_slaughter_weekly():
    """Weekly cattle slaughter for dashboard sparkline."""
    return query_to_df("""
        SELECT slaughter_date, monday_of_week, slaughter, week_ago, year_ago,
               week_to_date, year
        FROM slaughter
        WHERE source = 'harvest3' AND commodity = 'Cattle'
          AND period = 'Current' AND slaughter > 1000
        ORDER BY slaughter_date ASC
    """)


def get_hog_slaughter_weekly():
    """Weekly hog slaughter for dashboard sparkline."""
    return query_to_df("""
        SELECT slaughter_date, monday_of_week, slaughter, week_ago, year_ago,
               week_to_date, year
        FROM slaughter
        WHERE source = 'harvest3' AND commodity IN ('Hogs', 'Slaughter Hogs')
          AND period = 'Current' AND slaughter > 1000
        ORDER BY slaughter_date ASC
    """)


def get_cattle_cash_price():
    """National cash cattle price — last 52 weeks."""
    return query_to_df("""
        SELECT report_date, weighted_avg_price
        FROM cash_cattle
        WHERE class_description = 'ALL BEEF TYPE'
          AND selling_basis = 'LIVE DELIVERED'
          AND grade_description = 'Total all grades'
          AND weighted_avg_price BETWEEN 100 AND 400
        ORDER BY report_date ASC
    """)


def get_beef_cutout_dashboard():
    """Choice cutout last 52 weeks."""
    return query_to_df("""
        SELECT report_date, attribute, value
        FROM cutout_values
        WHERE attribute = 'Choice' AND value IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_pork_regional_prices():
    """National, Iowa/SMN and Western Cornbelt hog cash prices."""
    return query_to_df("""
        SELECT report_date, name, wtd_avg, price_5day, year
        FROM nearby_futures
        WHERE name IN ('National', 'IASWMN', 'Western Cornbelt')
          AND wtd_avg IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_pork_cutout_dashboard():
    """Pork carcass value last 52 weeks."""
    return query_to_df("""
        SELECT report_date, commodity, value
        FROM pork_primals
        WHERE commodity = 'Carcass' AND value > 0
        ORDER BY report_date ASC
    """)


def get_feed_futures_dashboard():
    """Corn and soy futures closes for dashboard."""
    return query_to_df("""
        SELECT commodity, symbol, contract_month, trade_date, close_price
        FROM feed_futures
        WHERE close_price IS NOT NULL AND close_price > 0
        ORDER BY commodity, trade_date ASC
    """)


def get_harvest_usda():
    """Hog carcass weights from harvest_usda table."""
    return query_to_df("""
        SELECT report_date, avg_carcass_weight, wtd_avg_net_price,
               week_of_year, year
        FROM harvest_usda
        WHERE avg_carcass_weight IS NOT NULL
        ORDER BY report_date ASC
    """)


def get_sow_harvest():
    """Weekly sow slaughter head counts."""
    return query_to_df("""
        SELECT report_date, volume, year
        FROM sow_harvest
        WHERE volume IS NOT NULL
        ORDER BY report_date ASC
    """)