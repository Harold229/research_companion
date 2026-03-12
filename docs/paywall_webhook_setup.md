# Setup du webhook Google Sheets pour le faux paywall

## 1. Créer le Google Sheet

Créer un Google Sheet avec deux onglets :

- `paywall_events`
- `interest_leads`

Les en-têtes seront créés automatiquement par le script Apps Script si besoin.

## 2. Créer le script Apps Script

1. Ouvrir le Google Sheet.
2. Aller dans `Extensions` > `Apps Script`.
3. Remplacer le contenu du projet par le fichier [integrations/google_sheets_paywall_webhook.gs](/Users/haroldtankpinou/Documents/PYTHON_PROJECT/research-companion/integrations/google_sheets_paywall_webhook.gs).
4. Dans `Project Settings` > `Script properties`, ajouter :
   - `SPREADSHEET_ID` = identifiant du Google Sheet

## 3. Déployer le Web App

1. Cliquer sur `Deploy` > `New deployment`.
2. Choisir `Web app`.
3. Exécuter en tant que : `Me`.
4. Accès : `Anyone with the link`.
5. Déployer puis copier l’URL du Web App.

## 4. Brancher l’app Streamlit

Configurer `PAYWALL_WEBHOOK_URL` :

- en local via variable d’environnement
- ou dans `.streamlit/secrets.toml`

Exemple `secrets.toml` :

```toml
PAYWALL_WEBHOOK_URL = "https://script.google.com/macros/s/.../exec"
```

## 5. Vérifier les événements critiques

Depuis l’app :

1. Cliquer sur `Copier le pack complet` pour déclencher `paywall_view`.
2. Choisir un prix pour déclencher `paywall_price_selected`.
3. Saisir un email puis cliquer sur `Être recontacté` pour déclencher `paywall_email_submitted`.
4. Cliquer sur `Pas maintenant` pour déclencher `paywall_dismissed`.
5. Répondre à la micro-question pour déclencher `paywall_refusal_reason_submitted`.

## 6. Vérifier le contenu du Sheet

Dans `paywall_events`, vérifier au minimum :

- `timestamp`
- `session_id`
- `event_name`
- `question_initiale`
- `question_reformulee`
- `type_question`
- `framework`
- `wide_count`
- `narrow_count`
- `is_identical`
- `price_shown`
- `price_selected`
- `email`
- `comment`
- `refusal_reason`
- `source`

Dans `interest_leads`, vérifier au minimum :

- `timestamp`
- `session_id`
- `event_name`
- `question_initiale`
- `question_reformulee`
- `type_question`
- `framework`
- `price_selected`
- `email`
- `comment`
- `refusal_reason`
- `source`

## 7. Test local sans Google Sheets

Pour valider le format d’envoi et la robustesse côté app sans dépendre de Google :

```bash
python research-companion/scripts/validate_paywall_tracking.py
```

Ce script :

- simule les événements critiques vers un faux webhook local
- vérifie que les payloads arrivent complets
- vérifie qu’un échec webhook reste non bloquant
