"""Behavioral checks for provenance, graph invariants, and reproducible output."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from model import OUTPUT_FILES, SCHEMA_DIR, check_data, read_json
from render_mermaid import escape_label, mermaid_id, render
from schema_check import SchemaChecker, SchemaError
from validate import validate_directory


def fixture() -> tuple[dict, dict]:
    confidence = {'level': 'high', 'rationale': 'The supplied source explicitly states this.'}
    def node(identifier, kind, level='L1'):
        return {'id':identifier,'type':kind,'title':identifier,'summary':'A grounded explanation.',
                'importance':'core','learning_depth':'orientation','level':level,'source_refs':['s1'],
                'attribution':'author_claim','confidence':copy.deepcopy(confidence)}
    nodes = [node('problem','problem'), node('idea','insight'), node('system','architecture'),
             node('measurement','evidence','L2'), node('pattern','pattern','L3')]
    nodes[3]['attribution'] = 'direct_evidence'
    nodes[3]['details'] = {'evidence_kind':'empirical','scope':'A single synthetic workload.',
                           'result':'The observed operation count decreased.','limitations':['No independent replication.']}
    nodes[4]['attribution'] = 'ai_inference'
    nodes[4]['details'] = {'applicability':['The same bottleneck dominates.'],
                           'failure_modes':['The bottleneck moves elsewhere.']}
    def edge(identifier,start,end,relation,attribution='author_claim'):
        return {'id':identifier,'source_id':start,'target_id':end,'relation':relation,
                'rationale':'The cited passage explains this relation.','evidence_refs':['s1'],
                'attribution':attribution,'confidence':copy.deepcopy(confidence)}
    data = {'schema_version':'1.0','document':{'id':'demo','title':'Synthetic material','source_type':'markdown',
        'uri':'source.md','coverage':{'status':'complete','inspected_units':['lines 1–30'],'gaps':[]}},
        'source_refs':[{'id':'s1','origin':'primary','uri':'source.md','kind':'lines','locator':'lines 1–30'}],
        'nodes':nodes}
    graph = {'schema_version':'1.0','document_id':'demo','nodes_file':'knowledge_nodes.json',
        'spine':[{'node_id':x,'why_next':'This question motivates the following step.'} for x in ('problem','idea','system')],
        'views':{'L1':['problem','idea','system'],'L2':['problem','idea','system','measurement'],
                 'L3':[n['id'] for n in nodes]},
        'edges':[edge('e1','problem','idea','motivates'),edge('e2','system','idea','implements'),
                 edge('e3','measurement','system','supports'),edge('e4','system','pattern','generalizes_to','ai_inference')]}
    return data,graph


def write_output(directory: Path, data: dict, graph: dict) -> None:
    for name,payload in [('knowledge_nodes.json',data),('knowledge_graph.json',graph)]:
        (directory/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'overview.md').write_text('# Overview\n\n'+ '\n'.join(f'[{name}]({name})' for name in OUTPUT_FILES[1:]),encoding='utf-8')
    (directory/'document_map.md').write_text('# Document map\n\n[s:s1] [Original](source.md), lines 1–30.\n',encoding='utf-8')
    (directory/'knowledge_spine.md').write_text('# Spine\n\n'+''.join(f'## {i}. Step [n:{step["node_id"]}]\n\nGrounded explanation. [s:s1]\n\n' for i,step in enumerate(graph['spine'],1)),encoding='utf-8')
    (directory/'architecture_analysis.md').write_text('# Architecture\n\n## System [n:system]\n\nExplanation. [s:s1]\n',encoding='utf-8')
    (directory/'design_patterns.md').write_text('# Patterns\n\n[n:pattern] is an AI inference with limits. [s:s1]\n',encoding='utf-8')
    (directory/'knowledge_graph.mmd').write_text(render(data,graph),encoding='utf-8')


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.data,self.graph = fixture()

    def assert_invalid(self, expected):
        errors,_ = check_data(self.data,self.graph)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_bundled_examples_are_complete_and_consistent(self):
        examples=sorted((SCRIPTS.parent/'examples').glob('*/expected'))
        self.assertTrue(examples)
        for directory in examples:
            with self.subTest(example=directory.parent.name):
                self.assertTrue((directory.parent/'source.md').is_file())
                errors,_=validate_directory(directory)
                self.assertEqual(errors,[])

    def test_valid_bundle_round_trip_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            write_output(directory,self.data,self.graph)
            self.assertEqual(validate_directory(directory),([],[]))
            completed=subprocess.run([sys.executable,'-B',str(SCRIPTS/'validate.py'),str(directory)],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertIn('source completeness',completed.stdout)

    def test_missing_evidence_scope_and_pattern_boundaries_rejected(self):
        del self.data['nodes'][3]['details']['scope']
        self.data['nodes'][4]['details']['failure_modes']=[]
        self.assert_invalid('missing required field scope')
        self.assert_invalid('requires at least 1 items')

    def test_invalid_enum_extra_fields_and_blank_explanations_rejected(self):
        self.data['nodes'][0]['importance']='high'
        self.data['nodes'][0]['unrecognized']=True
        self.graph['edges'][0]['rationale']='   '
        self.assert_invalid('value is not in')
        self.assert_invalid('unknown field unrecognized')
        self.assert_invalid('does not match')

    def test_missing_provenance_never_defaulted(self):
        del self.graph['edges'][0]['attribution']
        self.data['nodes'][1]['source_refs']=[]
        self.assert_invalid('missing required field attribution')
        self.assert_invalid('requires at least 1 items')

    def test_dangling_references_and_duplicate_ids_rejected(self):
        self.data['nodes'][0]['source_refs']=['missing_source']
        self.data['nodes'].append(copy.deepcopy(self.data['nodes'][1]))
        self.graph['edges'][1]['target_id']='missing_node'
        self.assert_invalid('unknown source ref missing_source')
        self.assert_invalid('duplicate IDs')
        self.assert_invalid('unknown endpoint')

    def test_coverage_declaration_cannot_hide_missing_pages(self):
        self.data['document']['coverage']['gaps']=[{'location':'Figure 4','reason':'Image unavailable','impact':'Cannot verify flow direction'}]
        self.assert_invalid('complete cannot have gaps')
        self.data['document']['coverage']['status']='partial'
        errors,warnings=check_data(self.data,self.graph)
        self.assertEqual(errors,[])
        self.assertTrue(any('partial' in x for x in warnings))
        self.data['document']['coverage']['gaps']=[]
        self.assert_invalid('partial must explain')

    def test_shared_spine_and_cumulative_views_enforced(self):
        self.graph['spine'].append(copy.deepcopy(self.graph['spine'][0]))
        self.graph['views']['L2']=['measurement']
        self.assert_invalid('spine: duplicate')
        self.assert_invalid('views.L2')

    def test_support_and_abstraction_directions_checked(self):
        self.graph['edges'][2]['source_id']='system'
        self.graph['edges'][2]['target_id']='measurement'
        self.graph['edges'][3]['source_id']='pattern'
        self.graph['edges'][3]['target_id']='system'
        self.assert_invalid('supports must start')
        self.assert_invalid('generalizes_to must end')

    def test_symmetric_duplicate_and_containment_cycle_rejected(self):
        one=copy.deepcopy(self.graph['edges'][0])
        one.update(id='c1',relation='contrasts_with')
        two=copy.deepcopy(one)
        two.update(id='c2',source_id=one['target_id'],target_id=one['source_id'])
        self.graph['edges'] += [one,two]
        self.assert_invalid('duplicate semantic edge')
        one['relation']=two['relation']='part_of'
        self.assert_invalid('containment relationships contain a cycle')

    def test_mutual_dependency_warns_without_assuming_it_is_wrong(self):
        edge=copy.deepcopy(self.graph['edges'][0])
        edge.update(id='d1',relation='depends_on')
        back=copy.deepcopy(edge)
        back.update(id='d2',source_id=edge['target_id'],target_id=edge['source_id'])
        self.graph['edges'] += [edge,back]
        errors,warnings=check_data(self.data,self.graph)
        self.assertEqual(errors,[])
        self.assertTrue(any('mutual dependence' in x for x in warnings))

    def test_empty_edge_set_and_isolated_nodes_are_valid(self):
        self.graph['edges']=[]
        self.assertEqual(check_data(self.data,self.graph),([],[]))
        rendered=render(self.data,self.graph)
        self.assertIn(mermaid_id('system'),rendered)
        self.assertNotIn('-->',rendered)

    def test_layer_filter_does_not_invent_transitive_edges(self):
        self.graph['edges']=[self.graph['edges'][2]]
        l1=render(self.data,self.graph)
        self.assertNotIn(mermaid_id('measurement'),l1)
        self.assertNotIn('-->',l1)
        l2=render(self.data,self.graph,'L2')
        self.assertIn(mermaid_id('measurement'),l2)
        self.assertIn('supports',l2)

    def test_focus_retains_only_visible_neighborhood(self):
        focused=render(self.data,self.graph,'L3','measurement',1)
        self.assertIn(mermaid_id('measurement'),focused)
        self.assertIn(mermaid_id('system'),focused)
        self.assertNotIn(mermaid_id('idea'),focused)
        with self.assertRaisesRegex(ValueError,'hidden'):
            render(self.data,self.graph,'L1','measurement',1)
        with self.assertRaisesRegex(ValueError,'nonnegative'):
            render(self.data,self.graph,'L3','measurement',-1)

    def test_mermaid_escapes_content_and_stable_ids_do_not_collide(self):
        self.data['nodes'][0]['title']='x"]\nclick evil "javascript:alert(1)" <script>&#35; %%'
        rendered=render(self.data,self.graph)
        self.assertNotIn('<script>',rendered)
        self.assertNotIn('\nclick',rendered)
        self.assertNotIn('"javascript:',rendered)
        self.assertIn('#34;',rendered)
        self.assertNotEqual(mermaid_id('a-b'),mermaid_id('a_b'))
        self.assertEqual(escape_label('one\ntwo'),'one two')

    def test_inference_and_comparison_render_without_false_direction(self):
        edge=self.graph['edges'][0]
        edge.update(relation='contrasts_with',attribution='ai_inference')
        rendered=render(self.data,self.graph)
        self.assertIn('---|"contrasts_with / AI inference"|',rendered)
        self.assertIn('linkStyle 0 stroke-dasharray',rendered)

    def test_stale_markdown_order_reference_and_mermaid_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            write_output(directory,self.data,self.graph)
            (directory/'knowledge_spine.md').write_text('## 1. Wrong [n:idea]\n\n[s:missing]\n',encoding='utf-8')
            (directory/'knowledge_graph.mmd').write_text('flowchart TD\n',encoding='utf-8')
            errors,_=validate_directory(directory)
            self.assertTrue(any('unknown s marker missing' in x for x in errors))
            self.assertTrue(any('graph.spine exactly' in x for x in errors))
            self.assertTrue(any('stale' in x for x in errors))

    def test_missing_outputs_and_invalid_json_return_cli_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'knowledge_nodes.json').write_text('{broken',encoding='utf-8')
            (directory/'knowledge_graph.json').write_text('{}',encoding='utf-8')
            completed=subprocess.run([sys.executable,'-B',str(SCRIPTS/'validate.py'),str(directory)],capture_output=True,text=True)
            self.assertEqual(completed.returncode,1)
            self.assertIn('Missing required output',completed.stderr)
            self.assertNotIn('Traceback',completed.stderr)

    def test_broken_deep_navigation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            write_output(directory,self.data,self.graph)
            overview=directory/'overview.md'
            overview.write_text(overview.read_text()+'\n[Details](architecture_analysis.md#node-system)\n',encoding='utf-8')
            errors,_=validate_directory(directory)
            self.assertTrue(any('navigation anchor' in x for x in errors))
            target=directory/'architecture_analysis.md'
            target.write_text('<a id="node-system"></a>\n'+target.read_text(),encoding='utf-8')
            self.assertEqual(validate_directory(directory),([],[]))

    def test_duplicate_json_keys_and_nonfinite_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.json'
            for payload in ('{"id":1,"id":2}','{"value":NaN}','{"value":1e999}'):
                path.write_text(payload,encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_json(path)

    def test_restricted_schema_checker_fails_on_unknown_vocabulary(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'schema.json').write_text('{"type":"object","unevaluatedProperties":false}',encoding='utf-8')
            with self.assertRaisesRegex(SchemaError,'Unsupported schema keywords'):
                SchemaChecker(directory).validate({},'schema.json')

    def test_restricted_schema_ref_cannot_escape_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'schema.json').write_text('{"$ref":"../outside.json"}',encoding='utf-8')
            with self.assertRaisesRegex(SchemaError,'stay inside'):
                SchemaChecker(directory).validate({},'schema.json')


if __name__=='__main__':
    unittest.main()
