import yaml, httpx, socket
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from valve.source.a2s import ServerQuerier, NoResponseError
from starlette.middleware.sessions import SessionMiddleware
from itsdangerous import Signer

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

with open("config.yaml") as f:
    config = yaml.safe_load(f)

DISCORD_API = "https://discord.com/api"
ALLOWED_USERS = config["discord"]["allowed_users"]

def is_admin(session):
    return session.get("user", {}).get("id") in ALLOWED_USERS

@app.get("/")
def home(request: Request):
    if not is_admin(request.session):
        return RedirectResponse("/login")
    return HTMLResponse(f"<h2>Welcome, {request.session['user']['username']}</h2><a href='/logout'>Logout</a>")

@app.get("/login")
def login():
    client_id = config["discord"]["client_id"]
    redirect_uri = config["discord"]["redirect_uri"]
    return RedirectResponse(f"{DISCORD_API}/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=identify")

@app.get("/auth/callback")
async def auth_callback(code: str, request: Request):
    data = {
        "client_id": config["discord"]["client_id"],
        "client_secret": config["discord"]["client_secret"],
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["discord"]["redirect_uri"],
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        token_res = await client.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers)
        token = token_res.json().get("access_token")
        user_res = await client.get(f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {token}"})
        request.session["user"] = user_res.json()
    return RedirectResponse("/")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/api/status")
def status(request: Request):
    if not is_admin(request.session):
        raise HTTPException(status_code=403)
    return {grid["id"]: is_port_open(grid["port"]) for grid in config["grids"]}

@app.get("/api/players")
def players(request: Request):
    if not is_admin(request.session):
        raise HTTPException(status_code=403)
    results = {}
    for grid in config["grids"]:
        try:
            with ServerQuerier(("127.0.0.1", grid["port"]), timeout=1) as server:
                info = server.info()
                players = server.players()
                results[grid["id"]] = {
                    "name": info["server_name"],
                    "map": info["map"],
                    "players": players["players"],
                    "max_players": info["max_players"]
                }
        except NoResponseError:
            results[grid["id"]] = {"error": "No response"}
        except Exception as e:
            results[grid["id"]] = {"error": str(e)}
    return results

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

@app.get("/api/leaderboard")
def leaderboard():
    with open("data/leaderboard.json") as f:
        return json.load(f)
