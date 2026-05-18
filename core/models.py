from django.db import models


class Slaughter(models.Model):
    report_date = models.DateField(null=True)
    commodity = models.CharField(max_length=100, null=True)
    class_name = models.CharField(max_length=100, null=True)
    period = models.CharField(max_length=50, null=True)
    slaughter = models.FloatField(null=True)
    week_ago = models.FloatField(null=True)
    year_ago = models.FloatField(null=True)
    week_to_date = models.FloatField(null=True)
    current_year_to_date = models.FloatField(null=True)
    previous_year_to_date = models.FloatField(null=True)
    pct_change = models.FloatField(null=True)
    week_of_year = models.FloatField(null=True)
    year = models.IntegerField(null=True)
    monday_of_week = models.DateField(null=True)
    slaughter_date = models.DateField(null=True)
    volume = models.FloatField(null=True)
    source = models.CharField(max_length=20, default='harvest3')  # 'harvest3' or 'historical'

    class Meta:
        db_table = 'slaughter'
        indexes = [
            models.Index(fields=['report_date']),
            models.Index(fields=['commodity', 'year']),
        ]


class CarcassWeight(models.Model):
    report_date = models.DateField(null=True)
    for_date_begin = models.DateField(null=True)
    purchase_type = models.CharField(max_length=100, null=True)
    head_count = models.IntegerField(null=True)
    avg_net_price = models.FloatField(null=True)
    avg_carcass_weight = models.FloatField(null=True)
    year = models.IntegerField(null=True)
    index_by_year = models.IntegerField(null=True)

    class Meta:
        db_table = 'carcass_weights'
        indexes = [models.Index(fields=['report_date'])]


class CutoutValue(models.Model):
    report_date = models.DateField(null=True)
    attribute = models.CharField(max_length=100, null=True)  # Choice or Select
    value = models.FloatField(null=True)
    trend = models.FloatField(null=True)
    week_of_year = models.CharField(max_length=20, null=True)
    year = models.IntegerField(null=True)
    index_by_year = models.IntegerField(null=True)

    class Meta:
        db_table = 'cutout_values'
        indexes = [
            models.Index(fields=['report_date']),
            models.Index(fields=['attribute']),
        ]


class CattlePrimal(models.Model):
    report_date = models.DateField(null=True)
    primal_desc = models.CharField(max_length=100, null=True)
    choice_600_900 = models.FloatField(null=True)
    select_600_900 = models.FloatField(null=True)
    week_of_year = models.IntegerField(null=True)
    year = models.IntegerField(null=True)
    start_of_week = models.DateField(null=True)
    end_of_week = models.DateField(null=True)

    class Meta:
        db_table = 'cattle_primal'
        indexes = [models.Index(fields=['report_date', 'primal_desc'])]


class CashCattle(models.Model):
    report_date = models.DateField(null=True)
    class_description = models.CharField(max_length=100, null=True)
    selling_basis = models.CharField(max_length=100, null=True)
    grade_description = models.CharField(max_length=100, null=True)
    weighted_avg_price = models.FloatField(null=True)
    year = models.IntegerField(null=True)
    index_by_year = models.IntegerField(null=True)

    class Meta:
        db_table = 'cash_cattle'
        indexes = [
            models.Index(fields=['report_date']),
            models.Index(fields=['class_description', 'selling_basis']),
        ]


class NearbyFutures(models.Model):
    report_date = models.DateField(null=True)
    purchase_type = models.CharField(max_length=100, null=True)
    price_5day = models.FloatField(null=True)
    name = models.CharField(max_length=100, null=True)
    year = models.IntegerField(null=True)
    wtd_avg = models.FloatField(null=True)
    avg = models.FloatField(null=True)

    class Meta:
        db_table = 'nearby_futures'
        indexes = [models.Index(fields=['report_date', 'name'])]


class FuturesEndpoint(models.Model):
    commodity = models.CharField(max_length=100, null=True)
    month = models.CharField(max_length=20, null=True)
    year = models.IntegerField(null=True)
    trading_day = models.DateField(null=True)
    close = models.FloatField(null=True)
    commodity_month = models.CharField(max_length=50, null=True)
    month_name = models.CharField(max_length=20, null=True)
    week_of_year = models.FloatField(null=True)
    symbol = models.CharField(max_length=50, null=True)

    class Meta:
        db_table = 'futures_endpoint'
        indexes = [models.Index(fields=['trading_day', 'commodity'])]


class LRPQuote(models.Model):
    commodity = models.CharField(max_length=100, null=True)
    coverage_level_percent = models.FloatField(null=True)
    coverage_price = models.FloatField(null=True)
    end_date = models.DateField(null=True)
    endorsement_length = models.IntegerField(null=True)
    expected_ending_value = models.FloatField(null=True)
    head_count = models.IntegerField(null=True)
    livestock_rate = models.FloatField(null=True)
    per_head_premium = models.FloatField(null=True)
    per_cwt_premium = models.FloatField(null=True)
    producer_premium = models.IntegerField(null=True)
    subsidy_percent = models.FloatField(null=True)
    target_weight = models.FloatField(null=True)
    futures_price = models.FloatField(null=True)
    cme_premium = models.FloatField(null=True)
    strike = models.IntegerField(null=True)
    grouping_date = models.IntegerField(null=True)
    weekdays_to_expiration = models.IntegerField(null=True)
    expiration_date = models.DateField(null=True)
    sales_effective_date = models.IntegerField(null=True)

    class Meta:
        db_table = 'lrp_quotes'
        indexes = [models.Index(fields=['commodity', 'coverage_level_percent'])]


class LRPFutures(models.Model):
    previous = models.FloatField(null=True)
    symbol = models.CharField(max_length=50, null=True)
    grouping_date = models.IntegerField(null=True)
    name = models.CharField(max_length=100, null=True)
    type = models.CharField(max_length=50, null=True)
    commodity = models.CharField(max_length=100, null=True)

    class Meta:
        db_table = 'lrp_futures'


class WASDEReport(models.Model):
    wasde_number = models.IntegerField(null=True)
    report_date = models.DateField(null=True)
    report_title = models.CharField(max_length=200, null=True)
    attribute = models.CharField(max_length=200, null=True)
    commodity = models.CharField(max_length=100, null=True)
    region = models.CharField(max_length=100, null=True)
    market_year = models.CharField(max_length=20, null=True)
    proj_est_flag = models.CharField(max_length=20, null=True)
    value = models.FloatField(null=True)
    unit = models.CharField(max_length=100, null=True)
    release_date = models.DateField(null=True)
    forecast_year = models.IntegerField(null=True)
    forecast_month = models.IntegerField(null=True)
    market_date = models.CharField(max_length=50, null=True)
    is_latest_two_dates = models.IntegerField(null=True)

    class Meta:
        db_table = 'wasde_reports'
        indexes = [
            models.Index(fields=['report_date', 'commodity']),
            models.Index(fields=['commodity', 'attribute']),
        ]


class CowHarvest(models.Model):
    report_date = models.DateField(null=True)
    class_name = models.CharField(max_length=100, null=True)
    volume = models.FloatField(null=True)
    unit = models.CharField(max_length=50, null=True)
    year = models.IntegerField(null=True)
    index_by_year = models.IntegerField(null=True)

    class Meta:
        db_table = 'cow_harvest'
        indexes = [models.Index(fields=['report_date', 'class_name'])]


class PorkPrimal(models.Model):
    report_date = models.DateField(null=True)
    commodity = models.CharField(max_length=100, null=True)
    value = models.FloatField(null=True)
    week_of_year = models.IntegerField(null=True)
    year = models.IntegerField(null=True)
    start_of_week = models.DateField(null=True)
    end_of_week = models.DateField(null=True)

    class Meta:
        db_table = 'pork_primals'
        indexes = [models.Index(fields=['report_date', 'commodity'])]


class HarvestUSDA(models.Model):
    report_date = models.DateField(null=True)
    for_date_begin = models.DateField(null=True)
    avg_carcass_weight = models.FloatField(null=True)
    avg_backfat = models.FloatField(null=True)
    wtd_avg_base = models.FloatField(null=True)
    wtd_avg_net_price = models.FloatField(null=True)
    week_of_year = models.IntegerField(null=True)
    year = models.IntegerField(null=True)

    class Meta:
        db_table = 'harvest_usda'
        indexes = [models.Index(fields=['report_date'])]
