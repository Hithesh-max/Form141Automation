import requests
import json
import pandas as pd
import io

# 1. Create a dummy excel file in memory
df = pd.DataFrame({
    'ClientCode': ['C001', 'C002'],
    'TaxPAN': ['ABCDE1234F', 'ZYXWV9876E'],
    'TaxAmount': [1500, 2500],
    'TDS': [150, 250]
})
excel_buffer = io.BytesIO()
df.to_excel(excel_buffer, index=False)
excel_buffer.seek(0)

# 2. Map columns
mapping = {
    "customer_code": "ClientCode",
    "pan": "TaxPAN",
    "amount": "TaxAmount",
    "tds_amount": "TDS"
}

# 3. Hit the API
print("Uploading file to API...")
response = requests.post(
    "http://localhost:8000/api/import/confirm",
    files={"file": ("test.xlsx", excel_buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    data={"mapping": json.dumps(mapping)}
)

print(response.status_code)
print(response.json())
