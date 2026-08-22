import httpx
import asyncio
import json
import time

async def verify():
    # Wait for backend to be ready
    await asyncio.sleep(2)
    
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8080", timeout=15.0) as c:
        # Step 5: Register
        print("=== 5. REGISTER ===")
        resp = await c.post("/api/v1/auth/register", json={
            "name": "E2E Test User",
            "company": "E2E Corp",
            "email": "e2e_test@example.com",
            "password": "SecurePassword123!",
        })
        if resp.status_code not in [200, 201]:
            if "already registered" in resp.text:
                print("User already exists, proceeding to login...")
            else:
                print(f"Register failed: {resp.status_code} {resp.text}")
        else:
            print(f"Register success: {resp.status_code}")

        # Step 6: Login
        print("\n=== 6. LOGIN ===")
        resp = await c.post("/api/v1/auth/login", json={
            "email": "e2e_test@example.com",
            "password": "SecurePassword123!",
        })
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return
        data = resp.json()
        access = data.get("access_token")
        headers = {"Authorization": f"Bearer {access}"}
        print(f"Login success, tokens received.")

        # Step 7: Settings -> correct user
        print("\n=== 7. SETTINGS (/auth/me) ===")
        resp = await c.get("/api/v1/auth/me", headers=headers)
        if resp.status_code != 200:
            print(f"Settings failed: {resp.status_code} {resp.text}")
        else:
            user = resp.json()
            print(f"Logged in as: {user.get('email')} (Org: {user.get('organization', {}).get('name')})")

        # Step 8: Dashboard -> real data
        print("\n=== 8. DASHBOARD ===")
        resp = await c.get("/api/v1/dashboard/summary", headers=headers)
        if resp.status_code != 200:
            print(f"Dashboard failed: {resp.status_code} {resp.text}")
        else:
            dash = resp.json()
            print(f"Dashboard loaded. Scans this week: {dash.get('scansThisWeek')}, Safe packages: {dash.get('safePackages')}")

        # Step 9: Create repository
        print("\n=== 9. CREATE REPOSITORY ===")
        resp = await c.post("/api/v1/projects", headers=headers, json={
            "name": "e2e-test-repo",
            "description": "A test repository for E2E verification",
            "language": "Node.js",
            "visibility": "PRIVATE",
            "branch": "main",
            "url": "https://github.com/test/e2e-test-repo.git"
        })
        if resp.status_code not in [200, 201]:
            print(f"Create repo failed: {resp.status_code} {resp.text}")
            return
        repo = resp.json()
        repo_id = repo.get("id")
        print(f"Created repository ID: {repo_id}")

        # Step 10: Upload package.json
        print("\n=== 10. UPLOAD PACKAGE.JSON ===")
        package_json = """{
            "dependencies": {
                "lodash": "4.17.20",
                "express": "4.17.1"
            }
        }"""
        files = {'file': ('package.json', package_json, 'application/json')}
        resp = await c.post(f"/api/v1/projects/{repo_id}/artifacts", headers=headers, files=files)
        if resp.status_code not in [200, 201]:
            print(f"Artifact upload failed: {resp.status_code} {resp.text}")
            return
        artifact_id = resp.json().get("id")
        print(f"Artifact uploaded ID: {artifact_id}")

        resp = await c.post(f"/api/v1/projects/{repo_id}/scans", headers=headers, json={
            "artifact_id": artifact_id,
            "scan_type": "FULL",
            "configuration": {}
        })
        if resp.status_code not in [200, 201, 202]:
            print(f"Scan trigger failed: {resp.status_code} {resp.text}")
            return
        scan = resp.json()
        scan_id = scan.get("id")
        print(f"Scan triggered ID: {scan_id}")

        # Step 11: Scan -> QUEUED -> RUNNING -> COMPLETED
        print("\n=== 11. SCAN PROGRESSION ===")
        max_attempts = 15
        for i in range(max_attempts):
            resp = await c.get(f"/api/v1/projects/{repo_id}", headers=headers)
            status = resp.json().get("status")
            print(f"Poll {i+1}: Project status is {status}")
            if status in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(1)

        # Step 12: Packages -> dependencies appear
        print("\n=== 12. PACKAGES ===")
        resp = await c.get(f"/api/v1/dependencies?projectId={repo_id}", headers=headers)
        if resp.status_code != 200:
            print(f"Dependencies fetch failed: {resp.status_code} {resp.text}")
        else:
            deps = resp.json().get("items", [])
            print(f"Found {len(deps)} dependencies.")

        # Step 13: Vulnerabilities -> fixture source shown honestly
        print("\n=== 13. VULNERABILITIES ===")
        resp = await c.get(f"/api/v1/vulnerabilities?projectId={repo_id}", headers=headers)
        if resp.status_code != 200:
            print(f"Vulnerabilities fetch failed: {resp.status_code} {resp.text}")
        else:
            vulns = resp.json().get("items", [])
            print(f"Found {len(vulns)} vulnerabilities.")

        # Step 14: Graph -> nodes/edges
        print("\n=== 14. GRAPH ===")
        resp = await c.get(f"/api/v1/projects/{repo_id}/graph", headers=headers)
        if resp.status_code != 200:
            print(f"Graph fetch failed: {resp.status_code} {resp.text}")
        else:
            graph = resp.json()
            print(f"Graph loaded with {len(graph.get('nodes', []))} nodes and {len(graph.get('edges', []))} edges.")

        # Step 16: Second organization -> no cross-tenant data
        print("\n=== 16. SECOND ORGANIZATION ===")
        resp = await c.post("/api/v1/auth/register", json={
            "name": "E2E Test User 2",
            "company": "E2E Corp 2",
            "email": "e2e_test2@example.com",
            "password": "SecurePassword123!",
        })
        if resp.status_code not in [200, 201] and "already registered" not in resp.text:
             print(f"Second user register failed: {resp.status_code} {resp.text}")
             
        resp = await c.post("/api/v1/auth/login", json={
            "email": "e2e_test2@example.com",
            "password": "SecurePassword123!",
        })
        data2 = resp.json()
        headers2 = {"Authorization": f"Bearer {data2.get('access_token')}"}
        
        resp = await c.get("/api/v1/projects", headers=headers2)
        repos2 = resp.json().get("items", [])
        print(f"Second user projects count: {len(repos2)} (Expected: 0)")

if __name__ == "__main__":
    asyncio.run(verify())
