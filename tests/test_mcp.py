import asyncio, os, sys
from harness.seed import seed
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def _session(db):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "harness.tools.mcp_server"],
        env={**os.environ, "LAB_DB": db, "TENANT_ID": "tenant_a"})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            res = await s.call_tool(
                "convert_units", {"value": 1.2, "from_unit": "Pa.s", "to_unit": "mPa.s"})
            return [t.name for t in tools.tools], res

def test_mcp_roundtrip(tmp_path):
    db = str(tmp_path / "m.db")
    seed(path=db, n=10).close()
    names, res = asyncio.run(_session(db))
    assert len(names) == 8
    assert "1200" in res.content[0].text

