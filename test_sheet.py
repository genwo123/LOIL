# test_sheet.py
from bot.utils.sheets import _get_spreadsheet

url = 'https://docs.google.com/spreadsheets/d/1GIHnWAE8gJggDeFVCGSFJgVml7DEAItmoe0TIBfLxS4/edit'
ss = _get_spreadsheet(url)
for ws in ss.worksheets():
    print(repr(ws.title))  