import os
import pandas as pd
import numpy as np
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import (
    Slaughter, CarcassWeight, CutoutValue, CattlePrimal,
    CashCattle, NearbyFutures, FuturesEndpoint,
    LRPQuote, LRPFutures, WASDEReport
)

DATA_DIR = settings.DATA_DIR


def clean(val):
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def parse_date(val):
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Load all CSVs into the database'

    def handle(self, *args, **kwargs):
        self.load_slaughter()
        self.load_carcass_weights()
        self.load_cutout()
        self.load_cattle_primal()
        self.load_cash_cattle()
        self.load_nearby_futures()
        self.load_futures_endpoint()
        self.load_lrp_quotes()
        self.load_lrp_futures()
        self.load_wasde()
        self.load_cow_harvest()
        self.load_pork_primals()
        self.load_harvest_usda()
        self.stdout.write(self.style.SUCCESS('All data loaded successfully.'))

    def load_slaughter(self):
        self.stdout.write('Loading slaughter data...')
        Slaughter.objects.all().delete()

        # Load Harvest_3
        df = pd.read_csv(DATA_DIR / 'Harvest 3.csv')
        df = df[df['period'] == 'Current']  # only current period rows
        objs = []
        for _, row in df.iterrows():
            objs.append(Slaughter(
                report_date=parse_date(row.get('report_date')),
                commodity=clean(row.get('commodity')),
                class_name=clean(row.get('class')),
                period=clean(row.get('period')),
                slaughter=clean(row.get('slaughter')),
                week_ago=clean(row.get('week_ago')),
                year_ago=clean(row.get('year_ago')),
                week_to_date=clean(row.get('week_to_date')),
                current_year_to_date=clean(row.get('current_year_to_date')),
                previous_year_to_date=clean(row.get('previous_year_to_date')),
                pct_change=clean(row.get('%_change')),
                week_of_year=clean(row.get('Week of Year')),
                year=clean(row.get('Year')),
                monday_of_week=parse_date(row.get('MondayOfWeek')),
                slaughter_date=parse_date(row.get('slaughter_date')),
                volume=clean(row.get('volume')),
                source='harvest3',
            ))
        Slaughter.objects.bulk_create(objs, batch_size=500)

        # Load Historical_Harvest to fill earlier years
        df2 = pd.read_csv(DATA_DIR / 'Historical Harvest.csv')
        objs2 = []
        for _, row in df2.iterrows():
            objs2.append(Slaughter(
                report_date=parse_date(row.get('report_date')),
                commodity=clean(row.get('commodity')),
                class_name=clean(row.get('class')),
                slaughter=clean(row.get('volume')),
                week_of_year=clean(row.get('IndexbyYear')),
                year=clean(row.get('Year')),
                monday_of_week=parse_date(row.get('MondayOfWeek')),
                slaughter_date=parse_date(row.get('slaughter_date')),
                volume=clean(row.get('volume')),
                source='historical',
            ))
        Slaughter.objects.bulk_create(objs2, batch_size=500)
        self.stdout.write(f'  Slaughter: {len(objs) + len(objs2)} rows')

    def load_carcass_weights(self):
        self.stdout.write('Loading carcass weights...')
        CarcassWeight.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Carcass Weights.csv')
        objs = [
            CarcassWeight(
                report_date=parse_date(row.get('report_date')),
                for_date_begin=parse_date(row.get('for_date_begin')),
                purchase_type=clean(row.get('purchase_type')),
                head_count=clean(row.get('head_count')),
                avg_net_price=clean(row.get('avg_net_price')),
                avg_carcass_weight=clean(row.get('avg_carcass_weight')),
                year=clean(row.get('Year')),
                index_by_year=clean(row.get('IndexbyYear')),
            ) for _, row in df.iterrows()
        ]
        CarcassWeight.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Carcass weights: {len(objs)} rows')

    def load_cutout(self):
        self.stdout.write('Loading cutout values...')
        CutoutValue.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Cutout (Select_Choice).csv')
        objs = [
            CutoutValue(
                report_date=parse_date(row.get('report_date')),
                attribute=clean(row.get('Attribute')),
                value=clean(row.get('Value')),
                trend=clean(row.get('trend')),
                week_of_year=str(clean(row.get('Week of Year'))),
                year=clean(row.get('Year')),
                index_by_year=clean(row.get('IndexbyYear')),
            ) for _, row in df.iterrows()
        ]
        CutoutValue.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Cutout: {len(objs)} rows')

    def load_cattle_primal(self):
        self.stdout.write('Loading cattle primal values...')
        CattlePrimal.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Cattle Primal Values.csv')
        objs = [
            CattlePrimal(
                report_date=parse_date(row.get('report_date')),
                primal_desc=clean(row.get('primal_desc')),
                choice_600_900=clean(row.get('choice_600_900')),
                select_600_900=clean(row.get('select_600_900')),
                week_of_year=clean(row.get('Week of Year')),
                year=clean(row.get('Year')),
                start_of_week=parse_date(row.get('StartOfWeek')),
                end_of_week=parse_date(row.get('EndOfWeek')),
            ) for _, row in df.iterrows()
        ]
        CattlePrimal.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Cattle primal: {len(objs)} rows')

    def load_cash_cattle(self):
        self.stdout.write('Loading cash cattle...')
        CashCattle.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Cash Cattle.csv')
        # Filter to most useful subset to keep table lean
        df = df[
            (df['selling_basis_description'] == 'LIVE DELIVERED') &
            (df['class_description'].isin(['STEER', 'HEIFER', 'ALL BEEF TYPE']))
        ]
        objs = [
            CashCattle(
                report_date=parse_date(row.get('report_date')),
                class_description=clean(row.get('class_description')),
                selling_basis=clean(row.get('selling_basis_description')),
                grade_description=clean(row.get('grade_description')),
                weighted_avg_price=clean(row.get('weighted_avg_price')),
                year=clean(row.get('Year')),
                index_by_year=clean(row.get('IndexbyYear')),
            ) for _, row in df.iterrows()
        ]
        CashCattle.objects.bulk_create(objs, batch_size=1000)
        self.stdout.write(f'  Cash cattle: {len(objs)} rows')

    def load_nearby_futures(self):
        self.stdout.write('Loading nearby futures...')
        NearbyFutures.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Nearby Futures.csv')
        objs = [
            NearbyFutures(
                report_date=parse_date(row.get('report_date')),
                purchase_type=clean(row.get('purchase_type')),
                price_5day=clean(row.get('price_5day')),
                name=clean(row.get('Name')),
                year=clean(row.get('Year')),
                wtd_avg=clean(row.get('wtd_avg')),
                avg=clean(row.get('avg')),
            ) for _, row in df.iterrows()
        ]
        NearbyFutures.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Nearby futures: {len(objs)} rows')

    def load_futures_endpoint(self):
        self.stdout.write('Loading futures endpoint...')
        FuturesEndpoint.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'EndPointList.csv')
        objs = [
            FuturesEndpoint(
                commodity=clean(row.get('Commodity')),
                month=clean(row.get('Month')),
                year=clean(row.get('Year')),
                trading_day=parse_date(row.get('tradingDay')),
                close=clean(row.get('close')),
                commodity_month=clean(row.get('Commodity Month')),
                month_name=clean(row.get('Month Name')),
                week_of_year=clean(row.get('WeekofYear')),
                symbol=clean(row.get('symbol')),
            ) for _, row in df.iterrows()
        ]
        FuturesEndpoint.objects.bulk_create(objs, batch_size=1000)
        self.stdout.write(f'  Futures endpoint: {len(objs)} rows')

    def load_lrp_quotes(self):
        self.stdout.write('Loading LRP quotes...')
        LRPQuote.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'LRP Quotes.csv')
        objs = [
            LRPQuote(
                commodity=clean(row.get('Commodity')),
                coverage_level_percent=clean(row.get('coverageLevelPercent')),
                coverage_price=clean(row.get('coveragePrice')),
                end_date=parse_date(row.get('endDate')),
                endorsement_length=clean(row.get('endorsementLength')),
                expected_ending_value=clean(row.get('expectedEndingValueAmount')),
                head_count=clean(row.get('headCount')),
                livestock_rate=clean(row.get('livestockRate')),
                per_head_premium=clean(row.get('perHeadPremium')),
                per_cwt_premium=clean(row.get('perHundredWeightPremium')),
                producer_premium=clean(row.get('producerPremiumAmount')),
                subsidy_percent=clean(row.get('subsidyPercent')),
                target_weight=clean(row.get('targetWeightQuantity')),
                futures_price=clean(row.get('Futures Price')),
                cme_premium=clean(row.get('CME Premium')),
                strike=clean(row.get('Strike')),
                grouping_date=clean(row.get('Grouping Date')),
                weekdays_to_expiration=clean(row.get('Weekdays to Expiration')),
                expiration_date=parse_date(row.get('Expiration Date')),
                sales_effective_date=clean(row.get('salesEffectiveDate')),
            ) for _, row in df.iterrows()
        ]
        LRPQuote.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  LRP quotes: {len(objs)} rows')

    def load_lrp_futures(self):
        self.stdout.write('Loading LRP futures...')
        LRPFutures.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'LRP Quotes Futures.csv')
        objs = [
            LRPFutures(
                previous=clean(row.get('Previous')),
                symbol=clean(row.get('Symbol.1')),
                grouping_date=clean(row.get('Grouping Date')),
                name=clean(row.get('Name')),
                type=clean(row.get('Type')),
                commodity=clean(row.get('Commodity')),
            ) for _, row in df.iterrows()
        ]
        LRPFutures.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  LRP futures: {len(objs)} rows')

    def load_wasde(self):
        self.stdout.write('Loading WASDE...')
        WASDEReport.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'WASDE.csv')
        objs = [
            WASDEReport(
                wasde_number=clean(row.get('WasdeNumber')),
                report_date=parse_date(row.get('ReportDate')),
                report_title=clean(row.get('ReportTitle')),
                attribute=clean(row.get('Attribute')),
                commodity=clean(row.get('Commodity')),
                region=clean(row.get('Region')),
                market_year=clean(row.get('MarketYear')),
                proj_est_flag=clean(row.get('ProjEstFlag')),
                value=clean(row.get('Value')),
                unit=clean(row.get('Unit')),
                release_date=parse_date(row.get('ReleaseDate')),
                forecast_year=clean(row.get('ForecastYear')),
                forecast_month=clean(row.get('ForecastMonth')),
                market_date=clean(row.get('Market Date')),
                is_latest_two_dates=clean(row.get('IsLatestTwoDates')),
            ) for _, row in df.iterrows()
        ]
        WASDEReport.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  WASDE: {len(objs)} rows')

    def load_cow_harvest(self):
        from core.models import CowHarvest
        self.stdout.write('Loading cow harvest...')
        CowHarvest.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Cow Harvest.csv')
        objs = [
            CowHarvest(
                report_date=parse_date(row.get('report_date')),
                class_name=clean(row.get('class')),
                volume=clean(row.get('volume')),
                unit=clean(row.get('unit')),
                year=clean(row.get('Year')),
                index_by_year=clean(row.get('IndexbyYear')),
            ) for _, row in df.iterrows()
        ]
        CowHarvest.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Cow harvest: {len(objs)} rows')

    def load_pork_primals(self):
        from core.models import PorkPrimal
        self.stdout.write('Loading pork primals...')
        PorkPrimal.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Pork Primal Values.csv')
        objs = [
            PorkPrimal(
                report_date=parse_date(row.get('report_date')),
                commodity=clean(row.get('Commodity')),
                value=clean(row.get('Value')),
                week_of_year=clean(row.get('Week of Year')),
                year=clean(row.get('Year')),
                start_of_week=parse_date(row.get('StartOfWeek')),
                end_of_week=parse_date(row.get('EndOfWeek')),
            ) for _, row in df.iterrows()
        ]
        PorkPrimal.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Pork primals: {len(objs)} rows')

    def load_harvest_usda(self):
        from core.models import HarvestUSDA
        self.stdout.write('Loading Harvest USDA...')
        HarvestUSDA.objects.all().delete()
        df = pd.read_csv(DATA_DIR / 'Harvest - USDA.csv')
        objs = [
            HarvestUSDA(
                report_date=parse_date(row.get('report_date')),
                for_date_begin=parse_date(row.get('for_date_begin')),
                avg_carcass_weight=clean(row.get('avg_carcass_weight')),
                avg_backfat=clean(row.get('avg_backfat')),
                wtd_avg_base=clean(row.get('wtd_avg_base')),
                wtd_avg_net_price=clean(row.get('wtd_avg_net_price')),
                week_of_year=clean(row.get('WeekofYear')),
                year=clean(row.get('Year')),
            ) for _, row in df.iterrows()
        ]
        HarvestUSDA.objects.bulk_create(objs, batch_size=500)
        self.stdout.write(f'  Harvest USDA: {len(objs)} rows')
