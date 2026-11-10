"""Thin wrappers over the Google Sheets and Drive APIs.

Auth: an OAuth "Desktop app" client you create in Google Cloud Console, saved as
private/secrets/client_secret.json. The first run opens a browser to sign in; the token is
cached in private/secrets/token.json. Both are gitignored via private/.
"""
from pathlib import Path

from .store import SECRETS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    # Full Drive scope so files you drop into the Inbox folder by hand are visible.
    "https://www.googleapis.com/auth/drive",
]
_services = {}


def _creds():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise SystemExit("Google libraries missing: pip install -r tools/requirements.txt")
    token, client = SECRETS / "token.json", SECRETS / "client_secret.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not client.exists():
            raise SystemExit(f"Missing {client}. See tools/README.md, 'Google setup'.")
        creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES).run_local_server(port=0)
        SECRETS.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def svc(name):
    if name not in _services:
        from googleapiclient.discovery import build
        _services[name] = build(name, "v4" if name == "sheets" else "v3", credentials=_creds(), cache_discovery=False)
    return _services[name]


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------- Sheets ----------------

def read_tab(sheet_id, tab, missing_ok=False):
    """(rows as {header: value}, header list). With missing_ok, a tab that doesn't exist yet
    reads as empty instead of failing (upgrade-sheet will add it)."""
    if missing_ok and tab not in list_tabs(sheet_id):
        return [], []
    rows = svc("sheets").spreadsheets().values().get(spreadsheetId=sheet_id, range=f"'{tab}'").execute().get("values", [])
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        out.append({h: (r[i] or "").strip() for i, h in enumerate(header) if h})
    return out, header


def write_cells(sheet_id, tab, header, row_index, fields):
    data = [{"range": f"'{tab}'!{col_letter(header.index(k))}{row_index + 2}", "values": [[v]]}
            for k, v in fields.items() if k in header]
    if data:
        svc("sheets").spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id, body={"valueInputOption": "RAW", "data": data}).execute()


def append_rows(sheet_id, tab, rows):
    svc("sheets").spreadsheets().values().append(
        spreadsheetId=sheet_id, range=f"'{tab}'!A1", valueInputOption="RAW",
        insertDataOption="INSERT_ROWS", body={"values": rows}).execute()


_tab_cache = {}


def _sheet_props(sheet_id):
    meta = svc("sheets").spreadsheets().get(spreadsheetId=sheet_id,
                                            fields="sheets(properties(sheetId,title,gridProperties))").execute()
    return {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}


def list_tabs(sheet_id):
    if sheet_id not in _tab_cache:
        _tab_cache[sheet_id] = list(_sheet_props(sheet_id))
    return _tab_cache[sheet_id]


def add_tab(sheet_id, title, header):
    """Create a tab with a bold, frozen header row."""
    resp = svc("sheets").spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
        {"addSheet": {"properties": {"title": title, "gridProperties": {"frozenRowCount": 1,
                                                                          "columnCount": max(26, len(header))}}}}]}).execute()
    sid = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
    svc("sheets").spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"'{title}'!A1", valueInputOption="RAW", body={"values": [header]}).execute()
    svc("sheets").spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}}]}).execute()
    _tab_cache.pop(sheet_id, None)


def add_columns(sheet_id, tab, current_header, new_headers):
    """Append header cells after the last existing column, growing the grid if needed."""
    props = _sheet_props(sheet_id)[tab]
    need = len(current_header) + len(new_headers)
    have = props["gridProperties"]["columnCount"]
    if need > have:
        svc("sheets").spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
            {"appendDimension": {"sheetId": props["sheetId"], "dimension": "COLUMNS", "length": need - have}}]}).execute()
    start = col_letter(len(current_header))
    svc("sheets").spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"'{tab}'!{start}1", valueInputOption="RAW",
        body={"values": [list(new_headers)]}).execute()


# ---------------- Drive ----------------

def create_folder(name, parent=None):
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        body["parents"] = [parent]
    return svc("drive").files().create(body=body, fields="id").execute()["id"]


def move(file_id, new_parent, new_name=None):
    d = svc("drive")
    old = ",".join(d.files().get(fileId=file_id, fields="parents").execute().get("parents", []))
    body = {"name": new_name} if new_name else {}
    d.files().update(fileId=file_id, addParents=new_parent, removeParents=old, body=body, fields="id").execute()


def list_folder(folder_id):
    q = f"'{folder_id}' in parents and trashed = false"
    files, token = [], None
    while True:
        r = svc("drive").files().list(q=q, fields="nextPageToken, files(id,name,mimeType,createdTime)",
                                      orderBy="createdTime desc", pageToken=token).execute()
        files += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return files


def download(file_id, dest: Path):
    from googleapiclient.http import MediaIoBaseDownload
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        dl = MediaIoBaseDownload(f, svc("drive").files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = dl.next_chunk()
    return dest


def upload(path: Path, folder_id, name=None, mime="image/png"):
    from googleapiclient.http import MediaFileUpload
    body = {"name": name or path.name, "parents": [folder_id]}
    return svc("drive").files().create(body=body, media_body=MediaFileUpload(str(path), mimetype=mime),
                                       fields="id").execute()["id"]


def replace_content(file_id, path: Path, mime="image/png"):
    """Overwrite an existing Drive file's contents, keeping its ID and sharing."""
    from googleapiclient.http import MediaFileUpload
    svc("drive").files().update(fileId=file_id, media_body=MediaFileUpload(str(path), mimetype=mime)).execute()


def write_doc(text, folder_id, title, doc_id=None):
    """Create or overwrite a Google Doc from plain text. Returns the doc ID."""
    import io
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(text.encode("utf-8")), mimetype="text/plain", resumable=False)
    d = svc("drive").files()
    if doc_id:
        d.update(fileId=doc_id, media_body=media).execute()
        return doc_id
    body = {"name": title, "parents": [folder_id], "mimeType": "application/vnd.google-apps.document"}
    return d.create(body=body, media_body=media, fields="id").execute()["id"]


def export_text(file_id, mime="text/markdown"):
    """Export a Google Doc as text (markdown by default)."""
    data = svc("drive").files().export(fileId=file_id, mimeType=mime).execute()
    return data.decode("utf-8") if isinstance(data, bytes) else data
