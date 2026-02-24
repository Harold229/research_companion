import gspread
from google.oauth2.service_account import credentials
from datetime import datetime 

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet():
    """
    Connexion au Google sheet via le compte de service
    """
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = credentials.Credentials.from_service_account_file(
       creds_dict, scopes=SCOPES)
    except:
        creds = Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPES
        )
    client = gspread.authorize(creds)
    sheet = client.open("Research Companion Feedback").sheet1
    return sheet

def save_feedback(level: str, population: str, intervention: str, 
                  outcome: str, comparaison: str, rating: int, comment: str):
    """
    Sauvegarder les retours utilisateurs dans le google sheet 
    """
    sheet = get_sheet()
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        level,
        population,
        intervention or "",
        outcome or "",
        comparaison or "",
        rating,
        comment
    ]
    
    sheet.append_row(row)

if __name__ == "__main__":
    save_feedback(
        level="Level 1",
        population="children with obesity",
        intervention="physical activity",
        outcome="BMI reduction",
        comparaison="",
        rating=5,
        comment="Test feedback"
    )
    print("Feedback sauvegardé !")