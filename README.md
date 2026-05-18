# AgriPulse — Setup & Run

## 1. Install dependencies
```
pip install -r requirements.txt
```

## 2. Configure environment
Copy `.env.example` to `.env` and fill in your values:
```
DATABASE_URL=your_neon_connection_string
OPENROUTER_API_KEY=your_openrouter_key
SECRET_KEY=any-random-string
DEBUG=True
```

## 3. Put CSVs in /data folder
Place all CSV files in the `data/` directory at project root.
Required files:
- Harvest_3.csv
- Historical_Harvest.csv
- Carcass_Weights.csv
- Cutout_Select_Choice.csv
- Cattle_Primal_Values.csv
- Cash_Cattle.csv
- Nearby_Futures.csv
- EndPointList.csv
- LRP_Quotes.csv
- LRP_Quotes_Futures.csv
- WASDE.csv

## 4. Run migrations (creates tables in Neon)
```
python manage.py makemigrations core
python manage.py migrate
```

## 5. Load all CSV data into Neon (one time only)
```
python manage.py load_data
```
This will take a few minutes. Once done, CSVs are no longer needed.

## 6. Run the server
```
python manage.py runserver
```

Open http://localhost:8000

## Notes
- AI insights are cached for 24 hours — first load of the day calls OpenRouter, rest serve from cache
- The chatbot uses the last 6 messages as conversation history
- To reload data after CSV updates, re-run `python manage.py load_data`
- OpenRouter model is set to `openai/gpt-4o` in settings.py — change `OPENROUTER_MODEL` to swap models
