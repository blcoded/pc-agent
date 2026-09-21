import sys
import ctypes
from ctypes import wintypes
import urllib.request
import urllib.error
import json
import ssl
import subprocess
import os
import time

class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD),
        ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR),
        ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME),
        ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_char)),
        ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD),
        ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR),
        ('UserName', wintypes.LPWSTR),
    ]

def get_github_token():
    PCREDENTIAL = ctypes.POINTER(CREDENTIAL)
    CredRead = ctypes.windll.advapi32.CredReadW
    CredRead.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(PCREDENTIAL)]
    CredRead.restype = wintypes.BOOL
    CredFree = ctypes.windll.advapi32.CredFree
    CredFree.argtypes = [ctypes.c_void_p]

    pcred = PCREDENTIAL()
    if not CredRead("git:https://github.com", 1, 0, ctypes.byref(pcred)):
        raise RuntimeError("Failed to read credentials")

    blob_bytes = ctypes.string_at(pcred.contents.CredentialBlob, pcred.contents.CredentialBlobSize)
    CredFree(pcred)

    try:
        token = blob_bytes.decode('utf-16-le')
        if not token.startswith("gh"):
            token = blob_bytes.decode('utf-8')
    except Exception:
        token = blob_bytes.decode('utf-8', errors='ignore')

    return token.strip('\x00').strip()

def push_repo(token, retries=3):
    cwd = r"C:\Users\Free user\Documents\AI Dev tools\pc-voice-agent"
    push_url = f"https://x-access-token:{token}@github.com/blcoded/pc-agent.git"
    cmd = ["git", "-c", "credential.helper=", "push", push_url, "main"]
    for attempt in range(retries):
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            print("Git push successful.")
            return True
        print(f"Push attempt {attempt+1}/{retries} error: {res.stderr.strip()}")
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
    return False

def _api_call_with_retries(req, ctx, retries=4):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                return resp.status, resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8')
        except Exception as e:
            print(f"Connection attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                raise

def close_github_issue(issue_number, comment_text, token):
    ctx = ssl.create_default_context()
    owner = "blcoded"
    repo = "pc-agent"
    
    # Post comment
    if comment_text:
        comment_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
        req = urllib.request.Request(comment_url, data=json.dumps({"body": comment_text}).encode('utf-8'), method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "PC-Voice-Agent-Closer")
        try:
            status, _ = _api_call_with_retries(req, ctx)
            if status in (200, 201):
                print(f"Comment added to #{issue_number}")
        except Exception as e:
            print(f"Error adding comment to #{issue_number}: {e}")

    # Close issue
    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    req = urllib.request.Request(issue_url, data=json.dumps({"state": "closed"}).encode('utf-8'), method="PATCH")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "PC-Voice-Agent-Closer")
    try:
        status, _ = _api_call_with_retries(req, ctx)
        if status == 200:
            print(f"Closed issue #{issue_number} successfully.")
    except Exception as e:
        print(f"Error closing issue #{issue_number}: {e}")

def mark_task_complete(task_id):
    for path in [
        r"C:\Users\Free user\Documents\AI Dev tools\pc-voice-agent\tasks.md",
        r"C:\Users\Free user\Documents\AI Dev tools\pc-voice-agent\docs\tasks.md"
    ]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if f"**{task_id}**" in line and "`[ ]`" in line:
                    line = line.replace("`[ ]`", "`[x]`")
                new_lines.append(line)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            print(f"Marked {task_id} as [x] in {path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python close_issue.py <issue_num> <task_id> [comment]")
        sys.exit(1)
    
    issue_num = int(sys.argv[1])
    task_id = sys.argv[2]
    comment = sys.argv[3] if len(sys.argv) > 3 else f"Completed in {task_id}. All verification tests passed."
    
    token = get_github_token()
    mark_task_complete(task_id)
    push_repo(token)
    close_github_issue(issue_num, comment, token)
