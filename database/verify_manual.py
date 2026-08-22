import httpx
import asyncio
import json

async def verify():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as c:
        # 1. Register
        print("=== REGISTER ===")
        resp = await c.post("/api/v1/auth/register", json={
            "name": "Manual Test User",
            "company": "Manual Corp",
            "email": "manual_test@example.com",
            "password": "ManualPass1!",
        })
        print(f"[{resp.status_code}] X-Request-ID: {resp.headers.get('x-request-id')}")
        data = resp.json()
        print(f"  user: {data.get('user', {}).get('email')}")
        print(f"  org: {data.get('user', {}).get('organization', {}).get('name')}")
        print(f"  role: {data.get('user', {}).get('role')}")
        access = data.get("access_token")
        refresh = data.get("refresh_token")

        # 2. Login
        print("\n=== LOGIN ===")
        resp = await c.post("/api/v1/auth/login", json={
            "email": "manual_test@example.com",
            "password": "ManualPass1!",
        })
        print(f"[{resp.status_code}] X-Request-ID: {resp.headers.get('x-request-id')}")
        data = resp.json()
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        print(f"  has access_token: {bool(access)}")
        print(f"  has refresh_token: {bool(refresh)}")

        # 3. /auth/me
        print("\n=== ME ===")
        resp = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        print(f"[{resp.status_code}] X-Request-ID: {resp.headers.get('x-request-id')}")
        print(f"  Body: {resp.text[:200]}")

        # 4. Refresh
        print("\n=== REFRESH ===")
        resp = await c.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        print(f"[{resp.status_code}] X-Request-ID: {resp.headers.get('x-request-id')}")
        new_data = resp.json()
        new_access = new_data.get("access_token")
        new_refresh = new_data.get("refresh_token")
        print(f"  new tokens issued: {bool(new_access and new_refresh)}")

        # 5. Logout
        print("\n=== LOGOUT ===")
        resp = await c.post("/api/v1/auth/logout",
            json={"refresh_token": new_refresh},
            headers={"Authorization": f"Bearer {new_access}"})
        print(f"[{resp.status_code}] X-Request-ID: {resp.headers.get('x-request-id')}")

        # 6. Verify system endpoints still work
        print("\n=== SYSTEM ENDPOINTS ===")
        for ep in ["/health", "/health/database", "/ready", "/api/v1", "/docs", "/openapi.json"]:
            resp = await c.get(ep)
            print(f"[{resp.status_code}] {ep} | X-Request-ID: {resp.headers.get('x-request-id')}")

if __name__ == "__main__":
    asyncio.run(verify())
