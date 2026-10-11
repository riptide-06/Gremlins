"""Drive adapter: owner OAuth creates files; the shared service identity edits.

Only direct children of the stored folder ID are exposed. Plain UTF-8 files keep
exact replacement understandable; native Docs and shortcuts are not followed.
"""
import json

from cryptography.fernet import Fernet
import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import httpx

from cubbies import Fault, digest, drive_file_id

SCOPE = "https://www.googleapis.com/auth/drive.file"
ROOT = "https://www.googleapis.com/drive/v3"
FIELDS = "id,name,mimeType,parents,trashed,size,version"


class Drive:
    def __init__(self, settings, repo):
        self.settings, self.repo = settings, repo

    def cipher(self):
        if not self.settings.token_key:
            raise Fault("Drive token encryption is not configured.")
        return Fernet(self.settings.token_key.encode())

    def seal(self, token):
        return self.cipher().encrypt(token.encode()).decode()

    def owner_token(self, user):
        refresh = self.cipher().decrypt(user["refresh_token"].encode()).decode()
        credentials = Credentials(None, refresh_token=refresh, token_uri="https://oauth2.googleapis.com/token",
                                  client_id=self.settings.client_id, client_secret=self.settings.client_secret)
        credentials.refresh(Request())
        return credentials.token

    def service_token(self):
        source, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials = impersonated_credentials.Credentials(source_credentials=source,
            target_principal=self.settings.service_account, target_scopes=["https://www.googleapis.com/auth/drive"], lifetime=300)
        credentials.refresh(Request())
        return credentials.token

    def request(self, method, path, *, token, **kwargs):
        headers = kwargs.pop("headers", {}) | {"Authorization": "Bearer " + token}
        response = httpx.request(method, path if path.startswith("https://") else ROOT + path,
                                 headers=headers, timeout=15, **kwargs)
        if response.status_code == 412:
            raise Fault("File changed. Read again before editing.")
        if response.status_code >= 400:
            # Google errors can contain filenames or contents. Never relay them.
            raise Fault("Drive operation failed (HTTP %s). Check account connection and folder sharing." % response.status_code)
        return response

    def file_id(self, value):
        return drive_file_id(value)

    def name(self, value):
        if not value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value) or "/" in value:
            raise Fault("Use a filename of 1–200 characters without slashes or control characters.")
        return value

    def setup(self, user):
        token = self.owner_token(user)
        if not user.get("folder"):
            # App property recovers onboarding interrupted before Firestore saves.
            found = self.request("GET", "/files", token=token, params={
                "q": "trashed=false and mimeType='application/vnd.google-apps.folder' and 'me' in owners and appProperties has { key='campusCubby' and value='v1' }",
                "fields": "files(id)", "pageSize": 100}).json()["files"]
            if found:
                user["folder"] = found[0]["id"]
            else:
                user["folder"] = self.request("POST", "/files", token=token, json={
                    "name": "My Cubby", "mimeType": "application/vnd.google-apps.folder",
                    "folderColorRgb": "#34a853", "appProperties": {"campusCubby": "v1"}}).json()["id"]
            self.repo.put("users", digest(user["email"]), user)
        folder = self.file_id(user["folder"])
        try:
            metadata = self.request("GET", "/files/" + folder, token=token, params={"fields": "trashed,mimeType,owners(emailAddress)"}).json()
        except Fault as exc:
            raise Fault("Cannot access your saved cubby folder. " + str(exc) +
                        " Restore it in Drive if deleted, then reconnect with the original account. "
                        "If permanently deleted, contact the service administrator. No replacement folder was created.") from None
        if (metadata.get("trashed") or metadata["mimeType"] != "application/vnd.google-apps.folder" or
                user["email"] not in {o.get("emailAddress", "").lower() for o in metadata.get("owners", [])}):
            raise Fault("Your saved cubby must be an untrashed folder owned by your connected account. "
                        "Restore it in Drive or return it to the original owner, then reconnect. "
                        "No replacement folder was created.")
        permissions = self.request("GET", f"/files/{folder}/permissions", token=token,
                                   params={"fields": "permissions(id,emailAddress,role)"}).json().get("permissions", [])
        existing = next((p for p in permissions if p.get("emailAddress") == self.settings.service_account), None)
        if not existing:
            self.request("POST", f"/files/{folder}/permissions", token=token,
                         params={"sendNotificationEmail": "false"},
                         json={"type": "user", "role": "writer", "emailAddress": self.settings.service_account})
        elif existing["role"] != "writer":
            self.request("PATCH", f"/files/{folder}/permissions/{self.file_id(existing['id'])}", token=token,
                         json={"role": "writer"})
        # Verify the actual shared identity can use the folder before login succeeds.
        self.request("GET", "/files/" + folder, token=self.service_token(), params={"fields": "id"})
        return user

    def allocate(self, user):
        return self.request("GET", "/files/generateIds", token=self.owner_token(user),
                            params={"count": 1, "space": "drive", "type": "files"}).json()["ids"][0]

    def create(self, user, name, text, file_id=None):
        self.name(name)
        if len(text.encode()) > 100000:
            raise Fault("File size limit is 100000 UTF-8 bytes.")
        metadata = {"name": name, "parents": [user["folder"]], "mimeType": "text/plain"}
        if file_id:
            metadata["id"] = self.file_id(file_id)
        # Multipart metadata + UTF-8 media creates a complete file in one request.
        import secrets
        boundary = "cubby_" + secrets.token_hex(24)
        content = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" + json.dumps(metadata) +
                   f"\r\n--{boundary}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n" + text + f"\r\n--{boundary}--\r\n").encode()
        return self.request("POST", "https://www.googleapis.com/upload/drive/v3/files", token=self.owner_token(user),
                            params={"uploadType": "multipart", "fields": "id,name,version"}, content=content,
                            headers={"Content-Type": "multipart/related; boundary=" + boundary}).json()

    def deliver(self, user, file_id, name, text):
        # Retry using the reserved Drive ID: no duplicate after a crash or timeout.
        token = self.service_token()
        response = httpx.get(ROOT + "/files/" + self.file_id(file_id), headers={"Authorization": "Bearer " + token}, timeout=15)
        if response.status_code == 404:
            self.create(user, name, text, file_id)
        elif response.status_code != 200:
            raise Fault("Cannot verify delivery. Retry with the same request_id.")
        else:
            self.checked(user, file_id, token)

    def list(self, user, cursor=""):
        folder = self.file_id(user["folder"])
        params = {"q": f"'{folder}' in parents and trashed=false", "fields": "nextPageToken,files(id,name,mimeType,version)", "pageSize": 100}
        if cursor:
            params["pageToken"] = cursor
        data = self.request("GET", "/files", token=self.service_token(), params=params).json()
        return {"files": data.get("files", []), "cursor": data.get("nextPageToken", "")}

    def checked(self, user, file_id, token):
        response = self.request("GET", "/files/" + self.file_id(file_id), token=token, params={"fields": FIELDS})
        data = response.json()
        if (user["folder"] not in data.get("parents", []) or data.get("trashed") or
                data["mimeType"] not in {"text/plain", "text/markdown", "application/json"}):
            raise Fault("Only direct text-file children of your cubby are accessible.")
        if int(data.get("size", 0)) > 100000:
            raise Fault("File exceeds the 100000-byte read limit.")
        return data, response.headers.get("etag")

    def read(self, user, file_id):
        token = self.service_token()
        data, etag = self.checked(user, file_id, token)
        text = self.media(file_id, token)
        after, _ = self.checked(user, file_id, token)
        if data["version"] != after["version"]:
            raise Fault("File changed during read. Retry.")
        return {"file_id": file_id, "name": data["name"], "text": text, "revision": str(data["version"])}

    def media(self, file_id, token):
        content = self.request("GET", "/files/" + file_id, token=token, params={"alt": "media"}).content
        if len(content) > 100000:
            raise Fault("File exceeds the 100000-byte read limit.")
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise Fault("Only UTF-8 text files are supported.") from None

    def edit(self, user, file_id, revision, search, replacement):
        token = self.service_token()
        data, etag = self.checked(user, file_id, token)
        if str(data["version"]) != revision:
            raise Fault("File changed. Read again before editing.")
        text = self.media(file_id, token)
        first = text.find(search) if search else -1
        if first < 0 or text.find(search, first + 1) >= 0:
            raise Fault("Search text must match exactly once.")
        updated = text.replace(search, replacement, 1).encode()
        if len(updated) > 100000:
            raise Fault("File size limit is 100000 UTF-8 bytes.")
        after, _ = self.checked(user, file_id, token)
        if str(after["version"]) != revision:
            raise Fault("File changed. Read again before editing.")
        return self.request("PATCH", "https://www.googleapis.com/upload/drive/v3/files/" + file_id, token=token,
                            params={"uploadType": "media", "fields": "id,version"}, content=updated,
                             headers={"Content-Type": "text/plain; charset=UTF-8"}).json()

    def rename(self, user, file_id, name):
        token = self.service_token()
        self.checked(user, file_id, token)
        return self.request("PATCH", "/files/" + file_id, token=token, json={"name": self.name(name)}, params={"fields": "id,name"}).json()

    def trash(self, user, file_id):
        # Drive writers cannot always trash another user's My Drive file. Use the
        # owner's narrowly scoped authorization after enforcing the same boundary.
        token = self.owner_token(user)
        self.checked(user, file_id, token)
        self.request("PATCH", "/files/" + file_id, token=token, json={"trashed": True})
        return {"trashed": file_id}
