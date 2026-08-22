import pandas as pd
import os

def generate_excel():
    data = [
        {
            "Household Name": "Family Smith",
            "Member Since": "2020-01-01",
            "Engagement Score": 0.8,
            "First Name": "John",
            "Last Name": "Smith",
            "Birth Date": "1980-05-15",
            "Gender": "m",
            "Occupation": "employed",
            "Education": "university",
            "Cultural Background": "",
            "Special Needs": False
        },
        {
            "Household Name": "Family Smith",
            "Member Since": "2020-01-01",
            "Engagement Score": 0.8,
            "First Name": "Jane",
            "Last Name": "Smith",
            "Birth Date": "1982-08-20",
            "Gender": "f",
            "Occupation": "employed",
            "Education": "university",
            "Cultural Background": "",
            "Special Needs": False
        },
        {
            "Household Name": "Family Smith",
            "Member Since": "2020-01-01",
            "Engagement Score": 0.8,
            "First Name": "Timmy",
            "Last Name": "Smith",
            "Birth Date": "2015-03-10",
            "Gender": "m",
            "Occupation": "student",
            "Education": "none",
            "Cultural Background": "",
            "Special Needs": False
        },
        {
            "Household Name": "Single Doe",
            "Member Since": "2023-06-01",
            "Engagement Score": 0.2,
            "First Name": "Alice",
            "Last Name": "Doe",
            "Birth Date": "1995-12-01",
            "Gender": "f",
            "Occupation": "student",
            "Education": "university",
            "Cultural Background": "International",
            "Special Needs": True
        }
    ]
    
    df = pd.DataFrame(data)
    file_path = os.path.join(os.path.dirname(__file__), "test_data.xlsx")
    df.to_excel(file_path, index=False)
    print(f"Created {file_path}")

if __name__ == "__main__":
    generate_excel()
