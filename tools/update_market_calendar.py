"""Refresh the Android exchange calendar without changing model parameters."""
import argparse,json
from pathlib import Path
import pandas_market_calendars as markets

def main():
 p=argparse.ArgumentParser();p.add_argument('--start',default='2025-12-01');p.add_argument('--end',default='2030-12-31');a=p.parse_args()
 schedule=markets.get_calendar('NYSE').schedule(start_date=a.start,end_date=a.end)
 data={'start':a.start,'end':a.end,'source':'pandas_market_calendars NYSE','sessions':[{'date':str(day.date()),'close':row.market_close.isoformat()} for day,row in schedule.iterrows()]}
 target=Path(__file__).resolve().parents[1]/'android/app/src/main/assets/market-calendar.json'
 target.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
 print('Exchange calendar sessions:',len(data['sessions']))
if __name__=='__main__':main()
