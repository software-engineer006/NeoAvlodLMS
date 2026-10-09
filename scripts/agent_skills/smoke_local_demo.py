"""Read-only local portal smoke after the real-data cutover; no synthetic auth."""

import asyncio

import httpx
from verify_real_cutover import main as verify_cutover


async def main() -> None:
    await verify_cutover()
    async with httpx.AsyncClient(trust_env=False) as client:
        for base, host in (("http://admin:3000", "localhost:3000"),
                           ("http://teacher:3001", "127.0.0.1:3001")):
            assert (await client.get(base, headers={"Host": host})).status_code == 200
            assert (await client.get(base + "/api/v1/ready", headers={"Host": host})).status_code == 200
    print("OK: both local portals and real-data cutover verified; no fake IDs or OTPs")


if __name__ == "__main__":
    asyncio.run(main())
