"""Read-only verification of the fixed skill taxonomy in the local dashboard."""
import asyncio
from collections import Counter
import json
import httpx
from sqlalchemy import select
from app.core.dashboard_database import DashboardSessionLocal, dashboard_database
from app.models.skill_config import SkillConfiguration

async def main():
    async with DashboardSessionLocal() as db:
        row = (await db.execute(select(SkillConfiguration).where(SkillConfiguration.id == 1))).scalar_one()
        assert row.taxonomy_version == 1 and row.taxonomy_backup
        before = row.taxonomy_backup
        assert before['revision'] == 3 and before['draft']['assignments'] == {}
        assert row.proposals == before['proposals']
        print(json.dumps({'revision': row.revision, 'roots': len(row.draft['nodes']),
            'assignments': len(row.draft['assignments']), 'per_root': dict(Counter(row.draft['assignments'].values())),
            'backup_revision': before['revision'], 'preserved_rejections': len(row.proposals)}, ensure_ascii=False))
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000/api/v1', timeout=30) as client:
        forest = (await client.get('/student/skill-tree', params={'user_id': 20586})).json()['skill_forest']
        root = next(r for r in forest if r['id'] == 'foundation')
        leaf = next(t for t in root['children'] if t['id'] == 'topic:4')
        ac = await client.get('/student/skill-tags/4/problems', params={'user_id': 20586, 'status': 'ac'})
        ac.raise_for_status()
        assert ac.json()['total'] == leaf['ac_count'] == 2
        full = await client.get('/student/skill-tags/4/problems', params={'user_id': 20586, 'page': 2})
        full.raise_for_status()
        assert full.json()['total'] == leaf['problem_count'] == 270 and full.json()['page'] == 2
        for time_range in ['7d', '30d']:
            tree = (await client.get('/student/skill-tree', params={'user_id': 20586, 'time_range': time_range})).json()
            tag = next(t for r in tree['skill_forest'] for t in r['children'] if t['id'] == 'topic:4')
            page = (await client.get('/student/skill-tags/4/problems', params={'user_id': 20586, 'time_range': time_range, 'status': 'ac'})).json()
            assert page['total'] == tag['ac_count']
        print('Catalog totals, AC filter and time ranges match forest metrics; no writes performed.')
    await dashboard_database.close()

asyncio.run(main())