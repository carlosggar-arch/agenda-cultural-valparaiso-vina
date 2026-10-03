"""Bind visual assertions to canonical work/image identity, never obsolete IDs."""
from copy import deepcopy
from pathlib import Path
import unittest
from test_production_probe_retry import load_smoke_module


def payload(module):
    return {'events': [
        {'id': f'regenerated-{i}', 'title': title,
         'image': {'url': './assets/event-images/valparaiso/' + filename}}
        for i, (_, filename, title) in enumerate(module.OFFICIAL_IMAGE_CASES)
    ]}


class CanonicalImageCaseIdentityTests(unittest.TestCase):
    def test_same_work_and_owned_file_resolve_regenerated_ids_without_mutation(self):
        module=load_smoke_module()
        data=payload(module)
        original=deepcopy(data)
        cases=module.resolve_official_image_cases(data)
        self.assertEqual(cases,tuple((f'regenerated-{i}',filename,title)
            for i,(_,filename,title) in enumerate(module.OFFICIAL_IMAGE_CASES)))
        self.assertEqual(data,original)

    def test_unproven_or_ambiguous_rebinding_remains_a_failure(self):
        for change in ('wrong_file','wrong_title','remote_file','missing','duplicate','same_id_wrong_image'):
            with self.subTest(change=change):
                module=load_smoke_module()
                data=payload(module)
                if change=='wrong_file': data['events'][0]['image']['url']='./assets/event-images/valparaiso/another.webp'
                elif change=='wrong_title': data['events'][0]['title']='Different work'
                elif change=='remote_file': data['events'][0]['image']['url']='https://untrusted.example/'+module.OFFICIAL_IMAGE_CASES[0][1]
                elif change=='missing': data['events'].pop(0)
                elif change=='duplicate': data['events'].append(deepcopy(data['events'][0]))
                elif change=='same_id_wrong_image':
                    data['events'][0]['id']=module.OFFICIAL_IMAGE_CASES[0][0]
                    data['events'][0]['image']['url']='./assets/event-images/valparaiso/another.webp'
                with self.assertRaisesRegex(ValueError,'OFFICIAL_IMAGE_CASE_IDENTITY'):
                    module.resolve_official_image_cases(data)

    def test_typographical_quotes_do_not_change_work_or_image(self):
        module=load_smoke_module()
        data=payload(module)
        data['events'][0]['title']='“'+data['events'][0]['title']+'”'
        self.assertEqual(module.resolve_official_image_cases(data)[0][0],'regenerated-0')

    def test_retired_reference_work_is_replaced_by_current_official_capabilities(self):
        module=load_smoke_module()
        data={'timezone':'America/Santiago','events':[
            {'id':f'current-{i}','title':f'Current official work {i}',
             'image':{'url':'./assets/event-images/valparaiso/'+str(i+1)*24+'.webp','relevance':'event_specific'},
             'schedule':{'mode':'multi_day','start':'2026-01-01','end':'2099-12-31'},
             'public_status':{'source_official':True}}
            for i in range(2)]}
        self.assertEqual({row[0] for row in module.resolve_official_image_cases(data)}, {'current-0','current-1'})

    def test_present_reference_with_null_image_cannot_be_hidden_by_another_work(self):
        module=load_smoke_module()
        data=payload(module)
        data['events'][0]['image']['url']=None
        data['events'].append({'id':'other','title':'Another work',
            'image':{'url':'./assets/event-images/valparaiso/'+'a'*24+'.webp','relevance':'event_specific'},
            'schedule':{'mode':'multi_day','start':'2026-01-01','end':'2099-12-31'}})
        with self.assertRaisesRegex(ValueError,'OFFICIAL_IMAGE_CASE_IDENTITY'):
            module.resolve_official_image_cases(data)

    def test_regression_is_required_even_for_verifier_only_prs(self):
        root=Path(__file__).resolve().parents[2]
        workflow=(root/'.github/workflows/pr-release.yml').read_text(encoding='utf-8')
        self.assertIn('python app/scripts/test_canonical_image_case_identity.py',workflow)
        self.assertIn('image_identity_result=$?',workflow)
        self.assertIn('image-identity=$(status "$image_identity_result")',workflow)


if __name__=='__main__':
    unittest.main()
