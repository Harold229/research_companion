"""
Lightweight Zotero integration for connection, collection browsing and target selection.
"""

import os

import requests
import streamlit as st


ZOTERO_API_ROOT = "https://api.zotero.org"


class ZoteroIntegrationError(Exception):
    pass


def _get_secret(name: str) -> str:
    try:
        return st.secrets[name].strip()
    except Exception:
        return os.getenv(name, "").strip()


def get_default_zotero_api_key() -> str:
    return _get_secret("ZOTERO_API_KEY")


def get_zotero_connection() -> dict:
    return st.session_state.get("zotero_connection") or {}


def clear_zotero_connection() -> None:
    for key in [
        "zotero_connection",
        "zotero_collections",
        "zotero_items_preview",
        "zotero_selected_collection_key",
    ]:
        st.session_state.pop(key, None)


def _headers(api_key: str) -> dict:
    return {
        "Zotero-API-Key": api_key,
        "Accept": "application/json",
    }


def validate_zotero_api_key(api_key: str) -> dict:
    if not api_key.strip():
        raise ZoteroIntegrationError("Clé API Zotero manquante.")

    response = requests.get(
        f"{ZOTERO_API_ROOT}/keys/current",
        headers=_headers(api_key),
        timeout=15,
    )
    if response.status_code == 401 or response.status_code == 403:
        raise ZoteroIntegrationError("Clé API Zotero invalide ou non autorisée.")
    if response.status_code >= 400:
        raise ZoteroIntegrationError("Connexion Zotero indisponible pour le moment.")

    data = response.json()
    user_id = data.get("userID")
    username = data.get("username") or data.get("name") or ""
    if not user_id:
        raise ZoteroIntegrationError("Impossible d'identifier la bibliothèque Zotero associée à cette clé.")

    return {
        "api_key": api_key.strip(),
        "user_id": str(user_id),
        "username": username or f"Utilisateur {user_id}",
        "library_type": "user",
        "library_label": username or f"Bibliothèque utilisateur {user_id}",
    }


def fetch_zotero_collections(connection: dict) -> list:
    response = requests.get(
        f"{ZOTERO_API_ROOT}/users/{connection['user_id']}/collections",
        headers=_headers(connection["api_key"]),
        params={"limit": 100},
        timeout=15,
    )
    if response.status_code == 404:
        raise ZoteroIntegrationError("Collections Zotero introuvables.")
    if response.status_code >= 400:
        raise ZoteroIntegrationError("Impossible de charger les collections Zotero.")

    collections = []
    for item in response.json():
        data = item.get("data", {})
        collections.append({
            "key": item.get("key") or data.get("key"),
            "name": data.get("name", "Collection sans titre"),
            "parentCollection": data.get("parentCollection"),
        })
    return collections


def fetch_zotero_items_preview(connection: dict, collection_key: str = "") -> list:
    params = {"limit": 20, "format": "json"}
    if collection_key:
        endpoint = f"{ZOTERO_API_ROOT}/users/{connection['user_id']}/collections/{collection_key}/items/top"
    else:
        endpoint = f"{ZOTERO_API_ROOT}/users/{connection['user_id']}/items/top"

    response = requests.get(
        endpoint,
        headers=_headers(connection["api_key"]),
        params=params,
        timeout=15,
    )
    if response.status_code >= 400:
        raise ZoteroIntegrationError("Impossible de charger les références Zotero.")

    items = []
    for item in response.json():
        data = item.get("data", {})
        creators = data.get("creators", [])
        creator_names = []
        for creator in creators[:3]:
            name = " ".join(part for part in [creator.get("firstName", ""), creator.get("lastName", "")] if part).strip()
            if not name:
                name = creator.get("name", "")
            if name:
                creator_names.append(name)

        items.append({
            "key": item.get("key"),
            "title": data.get("title", "Référence sans titre"),
            "itemType": data.get("itemType", ""),
            "date": data.get("date", ""),
            "creators": creator_names,
            "tags": [tag.get("tag") for tag in data.get("tags", []) if tag.get("tag")],
        })

    return items


def build_zotero_target_mapping(project: dict, export_data: dict, collection: dict, connection: dict) -> dict:
    return {
        "library": {
            "type": connection.get("library_type", "user"),
            "user_id": connection.get("user_id", ""),
            "username": connection.get("username", ""),
        },
        "target_collection": {
            "key": collection.get("key", ""),
            "name": collection.get("name", ""),
        },
        "project": {
            "id": project.get("id", ""),
            "title": project.get("title", ""),
        },
        "articles": export_data.get("articles", []),
    }
