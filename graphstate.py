#!/usr/bin/env python

# parsing state representing a subgraph
# initialized with dependency graph
#
from __future__ import absolute_import
import copy,sys,re
import cPickle
from parser import *
from common.util import *
from constants import *
from common.SpanGraph import SpanGraph
from common.AMRGraph import *
import numpy as np



class ActionError(Exception):
    pass    
    
class ActionTable(dict):
    '''to do'''
    def add_action(self,action_name):
        key =  len(self.keys())+1
        self[key] = action_name
    
class GraphState(object):
    """
    Starting from dependency graph, each state represents subgraph in parsing process
    Indexed by current node being handled
    """
    
    sent = None
    #abt_tokens = None
    deptree = None
    action_table = None
    #new_actions = None
    sentID = 0
    gold_graph = None
    model = None
    verbose = None
    
    
    def __init__(self,sigma,A):
        self.sigma = sigma
        self.idx = self.sigma.top()
        self.cidx = None
        self.beta = None
        #self.beta = Buffer(A.nodes[self.idx].children[:]) if self.idx != -1 else None
        #self.cidx = self.beta.top()
        #if self.beta:
        #    self.cidx = self.beta.top()
        #else:
        #    self.cidx = None
        self.A = A
        self.action_history = []

        #self.left_label_set = set([])
        #self._init_atomics()


    @staticmethod
    def init_state(instance,verbose=0):
        depGraph = SpanGraph.init_dep_graph(instance,instance.tokens)
        #depGraph.pre_merge_netag(instance)
        seq = []
        #if instance.sentID == 104:
        #    import pdb
        #    pdb.set_trace()
        for r in sorted(depGraph.multi_roots,reverse=True): seq += depGraph.postorder(root=r)
        #seq = uniqify(seq)
        seq.append(-1)
        sigma = Buffer(seq)        
        sigma.push(START_ID)

        GraphState.text = instance.text
        GraphState.sent = instance.tokens
        #GraphState.abt_tokens = {}
        GraphState.gold_graph = instance.gold_graph
        if GraphState.gold_graph: GraphState.gold_graph.abt_node_table = {}
        GraphState.deptree = depGraph
        GraphState.sentID = instance.comment['id'] if instance.comment else GraphState.sentID + 1
        GraphState.verbose = verbose
        
        if verbose > 1:
            print >> sys.stderr,"Sentence ID:%s, initial sigma:%s" % (GraphState.sentID,sigma)

        return GraphState(sigma,copy.deepcopy(depGraph))

    @staticmethod
    def init_action_table(actions):
        actionTable = ActionTable()
        for act_type,act_str in actions:
            actionTable[act_type] = act_str

        #GraphState.new_actions = set()
        GraphState.action_table = actionTable
    
    def _init_atomics(self):
        """
        atomics features for the initial state
        """
        
        # first parent of current node
        sp1 = GraphState.sent[self.A.nodes[self.idx].parents[0]] if self.A.nodes[self.idx].parents else NOT_ASSIGNED
        # immediate left sibling, immediate right sibling and second right sibling
        if sp1 != NOT_ASSIGNED and len(self.A.nodes[sp1['id']].children) > 1:
            children = self.A.nodes[sp1['id']].children
            idx_order = sorted(children).index(self.idx)
            slsb = GraphState.sent[children[idx_order-1]] if idx_order > 0 else NOT_ASSIGNED
            srsb = GraphState.sent[children[idx_order+1]] if idx_order < len(children)-1 else NOT_ASSIGNED
            sr2sb = GraphState.sent[children[idx_order+2]] if idx_order < len(children)-2 else NOT_ASSIGNED
        else:
            slsb = EMPTY
            srsb = EMPTY
            sr2sb = EMPTY
        
        '''
        # left first parent of current node
        slp1 = GraphState.sent[self.A.nodes[self.idx].parents[0]] if self.A.nodes[self.idx].parents and self.A.nodes[self.idx].parents[0] < self.idx else NOT_ASSIGNED
        # right last child of current child
        brc1 = GraphState.sent[self.deptree.nodes[self.cidx].children[-1]] if self.cidx and self.A.nodes[self.cidx].children and self.A.nodes[self.cidx].children[-1] > self.cidx  else NOT_ASSIGNED
        # left first parent of current child
        blp1 = GraphState.sent[self.A.nodes[self.cidx].parents[0]] if self.cidx and self.A.nodes[self.cidx].parents and self.A.nodes[self.cidx].parents[0] < self.cidx else NOT_ASSIGNED
        '''
        self.atomics = [{'id':tok['id'],
                         'form':tok['form'],
                         'lemma':tok['lemma'],
                         'pos':tok['pos'],
                         'ne':tok['ne'],
                         'rel':tok['rel'] if 'rel' in tok else EMPTY,
                         'sp1':sp1,
                         'slsb':slsb,
                         'srsb':srsb,
                         'sr2sb':sr2sb
                        } 
                        for tok in GraphState.sent] # atomic features for current state
        
    def pcopy(self):
        return cPickle.loads(cPickle.dumps(self,-1))
    
    def is_terminal(self):
        """done traverse the graph"""
        return self.idx == -1
    
    def is_permissible(self,action):
        #TODO
        return True

    def is_possible_align(self,currentIdx,goldIdx,ref_graph):
        '''
        tmp_state = self.pcopy()
        oracle = __import__("oracle").DetOracleSC()
        next_action,label = oracle.give_ref_action(tmp_state,ref_graph)
        while tmp_state.beta:
            next_action['edge_label'] = label
            tmp_state = tmp_state.apply(next_action)
            next_action,label = oracle.give_ref_action(tmp_state,ref_graph)
        '''
        #ref_children = [ref_graph.abt_node_table[c] if c in ref_graph.abt_node_table else c for c in ref_graph.nodes[goldIdx].children] 
        #return len(set(self.A.nodes[currentIdx].children) & set(ref_children)) > 1 or self.A.nodes[currentIdx].words[0][0].lower() == goldIdx
        if self.A.nodes[currentIdx].words[0].lower() in prep_list:
            return False
        return True

    def get_current_argset(self):
        if self.idx == START_ID:
            return set([])
        currentIdx = self.idx 
        currentNode = self.get_current_node()
        currentGraph = self.A
        # record the core arguments current node(predicate) have
        return set(currentGraph.get_edge_label(currentIdx,c) for c in currentNode.children if currentGraph.get_edge_label(currentIdx,c).startswith('ARG'))
    def get_possible_actions(self,train):

        if self.idx == START_ID:
            return [{'type':NEXT2}]
        
        actions = []
        currentIdx = self.idx 
        currentChildIdx = self.cidx
        currentNode = self.get_current_node()
        currentChild = self.get_current_child()
        currentGraph = self.A
        token_label_set = GraphState.model.token_label_set
        token_to_concept_table = GraphState.model.token_to_concept_table
        tag_codebook = GraphState.model.tag_codebook

        if isinstance(currentIdx,int): 
            current_tok_lemma = ','.join(tok['lemma'] for tok in GraphState.sent if tok['id'] in range(currentNode.start,currentNode.end))
            current_tok_form = ','.join(tok['form'] for tok in GraphState.sent if tok['id'] in range(currentNode.start,currentNode.end))
            current_tok_ne = GraphState.sent[currentIdx]['ne'] 
        else:
            current_tok_form = ABT_TOKEN['form']
            current_tok_lemma = ABT_TOKEN['lemma'] #if currentIdx != START_ID else START_TOKEN['lemma']
            current_tok_ne = ABT_TOKEN['ne'] #if currentIdx != START_ID else START_TOKEN['ne']
            
        #if self.action_history and self.action_history[-1]['type'] in [REPLACEHEAD,NEXT2,DELETENODE] and currentNode.num_parent_infer_in_chain < 3 and currentNode.num_parent_infer == 0:
            #actions.extend([{'type':INFER,'tag':z} for z in tag_codebook['ABTTag'].labels()])

        if currentChildIdx: # beta not empty
            #all_candidate_edge_labels = GraphState.model.rel_codebook.labels()

            #if current_tok_lemma in token_label_set:
            #    all_candidate_edge_labels.extend(list(token_label_set[current_tok_lemma]))
            #elif current_tok_ne not in ['O','NUMBER']:                
            #    all_candidate_edge_labels.extend(list(token_label_set[current_tok_ne]))
                #all_candidate_tags.extend(GraphState.model.tag_codebook['ETag'].labels()) 
            #else:
            #    all_candidate_tags.append(current_tok_lemma)  # for decoding

            if currentChildIdx == START_ID:
                if currentNode.num_parent_infer_in_chain < 3 and currentNode.num_parent_infer == 0:
                    actions = [{'type':NEXT1},{'type':INFER}]
                else:
                    actions = [{'type':NEXT1}]
                return actions

            if currentIdx != 0: # not root
                if not currentChild.SWAPPED:
                    #actions.extend([{'type':MERGE},{'type':REPLACEHEAD}])  
                    ##actions.extend([{'type':NEXT1,'edge_label':y} for y in all_candidate_edge_labels])
                    #actions.append({'type':NEXT1})
                #else:
                    #actions.extend([{'type':MERGE},{'type':REPLACEHEAD},{'type':SWAP}])
                    #actions.append({'type':NEXT1})
                    ##if len(currentChild.parents) > 1:
                    ##actions.append({'type':REATTACH,'parent_to_attach':None}) # this equals delete edge
                    actions.append({'type':SWAP})
                    actions.extend([{'type':REATTACH,'parent_to_attach':p} for p in currentGraph.get_possible_parent_constrained(currentIdx,currentChildIdx)])
                    
                    #actions.extend([{'type':NEXT1,'edge_label':y} for y in all_candidate_edge_labels])
                
                if isinstance(currentIdx,int) and isinstance(currentChildIdx,int):
                    actions.append({'type':MERGE})
                actions.extend([{'type':NEXT1},{'type':REPLACEHEAD}])  
                actions.extend({'type':REENTRANCE,'parent_to_add':x} for x in currentGraph.get_possible_reentrance_constrained(currentIdx,currentChildIdx))
            else:
                actions.extend([{'type':NEXT1}])
                #if len(currentChild.parents) > 1:
                #actions.append({'type':REATTACH,'parent_to_attach':None}) # this equals delete edge
                actions.extend([{'type':REATTACH,'parent_to_attach':p} for p in currentGraph.get_possible_parent_constrained(currentIdx,currentChildIdx)])
                #actions.extend({'type':ADDCHILD,'child_type':x} for x in currentGraph.get_possible_children_unconstrained(currentIdx))
        else:
            all_candidate_tags = []
            # MOD
            if current_tok_lemma in token_to_concept_table:
                all_candidate_tags.extend(list(token_to_concept_table[current_tok_lemma]))
                #all_candidate_tags.append(current_tok_lemma.lower())
            elif isinstance(currentIdx,int) and (current_tok_ne not in ['O','NUMBER'] or currentNode.end - currentNode.start > 1):                
                all_candidate_tags.extend(list(token_to_concept_table[current_tok_ne]))
                #all_candidate_tags.append(current_tok_lemma.lower())
                #all_candidate_tags.extend(GraphState.model.tag_codebook['ETag'].labels())
            elif current_tok_lemma == ABT_TOKEN['lemma']:
                #all_candidate_tags.extend(tag_codebook['ABTTag'].labels())
                pass
                #all_candidate_tags.extend(currentGraph.nodes[currentIdx].tag)
            else:
                all_candidate_tags.append(current_tok_lemma.lower())  # for decoding

            if isinstance(currentIdx,int) and 'frmset' in GraphState.sent[currentIdx] \
               and GraphState.sent[currentIdx]['frmset'] not in all_candidate_tags:
                all_candidate_tags.append(GraphState.sent[currentIdx]['frmset'])


            if not currentNode.children and currentIdx != 0:
                actions.append({'type':DELETENODE})
            actions.append({'type':NEXT2})
            actions.extend({'type':NEXT2,'tag':z} for z in all_candidate_tags)

        return actions

    def get_node_context(self,idx):
        # first parent of current node
        if self.A.nodes[idx].parents:
            p1 = GraphState.sent[self.A.nodes[idx].parents[0]] if isinstance(self.A.nodes[idx].parents[0],int) else ABT_TOKEN
            p1_brown_repr = BROWN_CLUSTER[p1['form']]
            p1['brown4'] = p1_brown_repr[:4] if len(p1_brown_repr) > 3 else p1_brown_repr
            p1['brown6'] = p1_brown_repr[:6] if len(p1_brown_repr) > 5 else p1_brown_repr
            p1['brown10'] = p1_brown_repr[:10] if len(p1_brown_repr) > 9 else p1_brown_repr
            p1['brown20'] = p1_brown_repr[:20] if len(p1_brown_repr) > 19 else p1_brown_repr
        else:
            p1 = NOT_ASSIGNED
        if isinstance(idx,int):
            prs1 = GraphState.sent[idx-1] if idx > 0 else NOT_ASSIGNED
            prs2 = GraphState.sent[idx-2] if idx > 1 else NOT_ASSIGNED
        else:
            prs1 = ABT_TOKEN
            prs2 = ABT_TOKEN
        

        # immediate left sibling, immediate right sibling and second right sibling
        if p1 != NOT_ASSIGNED and len(self.A.nodes[self.A.nodes[idx].parents[0]].children) > 1:
            children = self.A.nodes[self.A.nodes[idx].parents[0]].children
            idx_order = sorted(children).index(idx)
            if idx_order > 0:
                lsb = GraphState.sent[children[idx_order-1]] if isinstance(children[idx_order-1],int) else ABT_TOKEN
            else:
                lsb = NOT_ASSIGNED
            if idx_order < len(children)-1:
                rsb = GraphState.sent[children[idx_order+1]] if isinstance(children[idx_order+1],int) else ABT_TOKEN
            else: 
                rsb = NOT_ASSIGNED
            if idx_order < len(children)-2:
                r2sb = GraphState.sent[children[idx_order+2]] if isinstance(children[idx_order+2],int) else ABT_TOKEN
            else:
                r2sb = NOT_ASSIGNED
        else:
            lsb = EMPTY
            rsb = EMPTY
            r2sb = EMPTY

        return prs2,prs1,p1,lsb,rsb,r2sb
        
    def get_feature_context_window(self,action):
        """context window for current node and its child"""
        def isprep(token):
            return token['pos'] == 'IN' and token['rel'] == 'prep'
        def delta_func(tag_to_predict,tok_form):
            if isinstance(tag_to_predict,(ConstTag,ETag)):
                return 'ECTag'
            else:
                tok_form = tok_form.lower()
                tag_lemma = tag_to_predict.split('-')[0]
                if tag_lemma == tok_form:
                    return '1'
                i=0
                slength = len(tag_lemma) if len(tag_lemma) < len(tok_form) else len(tok_form)
                while i < slength and tag_lemma[i] == tok_form[i]:
                    i += 1
                if i == 0:
                    return '0'
                elif tok_form[i:]:
                    return tok_form[i:]
                elif tag_lemma[i:]:
                    return tag_lemma[i:]
                else:
                    assert False
            
        s0_atomics = GraphState.sent[self.idx].copy() if isinstance(self.idx,int) else ABT_TOKEN#GraphState.abt_tokens[self.idx]
        s0_brown_repr = BROWN_CLUSTER[s0_atomics['form']]
        s0_atomics['brown4'] = s0_brown_repr[:4] if len(s0_brown_repr) > 3 else s0_brown_repr
        s0_atomics['brown6'] = s0_brown_repr[:6] if len(s0_brown_repr) > 5 else s0_brown_repr
        s0_atomics['brown8'] = s0_brown_repr[:8] if len(s0_brown_repr) > 7 else s0_brown_repr
        s0_atomics['brown10'] = s0_brown_repr[:10] if len(s0_brown_repr) > 9 else s0_brown_repr
        s0_atomics['brown20'] = s0_brown_repr[:20] if len(s0_brown_repr) > 19 else s0_brown_repr

        
        #s0_atomics['pfx'] = s0_atomics['form'][:4] if len(s0_atomics['form']) > 3 else s0_atomics['form']
        sprs2,sprs1,sp1,slsb,srsb,sr2sb=self.get_node_context(self.idx)        
        s0_atomics['prs1']=sprs1
        s0_atomics['prs2']=sprs2
        s0_atomics['p1']=sp1
        s0_atomics['lsb']=slsb
        s0_atomics['rsb']=srsb
        s0_atomics['r2sb']=sr2sb
        s0_atomics['len']=self.A.nodes[self.idx].end - self.A.nodes[self.idx].start if isinstance(self.idx,int) else NOT_ASSIGNED
        #s0_atomics['cap']=s0_atomics['form'].istitle()
        s0_atomics['dch']=sorted([GraphState.sent[j]['form'].lower() if isinstance(j,int) else ABT_FORM for j in self.A.nodes[self.idx].del_child])
        s0_atomics['reph']=sorted([GraphState.sent[j]['form'].lower() if isinstance(j,int) else ABT_FORM for j in self.A.nodes[self.idx].rep_parent])
        #s0_atomics['nech'] = len(set(GraphState.sent[j]['ne'] if isinstance(j,int) else ABT_NE for j in self.A.nodes[self.idx].children) & INFER_NETAG) > 0
        #s0_atomics['isnom'] = s0_atomics['lemma'] in NOMLIST

        core_args = set([self.A.get_edge_label(self.idx,child) for child in self.A.nodes[self.idx].children if self.A.get_edge_label(self.idx,child).startswith('ARG') and child != self.cidx])
        s0_atomics['lsl']=str(sorted(core_args)) # core argument
        s0_atomics['arg0']='ARG0' in core_args
        s0_atomics['arg1']='ARG1' in core_args
        s0_atomics['arg2']='ARG2' in core_args

        # prop feature
        s0_atomics['frmset']=GraphState.sent[self.idx]['frmset'] if isinstance(self.idx,int) and 'frmset' in GraphState.sent[self.idx] else NOT_ASSIGNED

        # mod here
        # next2 specific features
        if not self.cidx:
            if 'tag' in action: # next2
                tag_to_predict = action['tag']
                s0_atomics['eqfrmset'] = s0_atomics['frmset'] == tag_to_predict if s0_atomics['frmset'] is not NOT_ASSIGNED else NOT_ASSIGNED
                s0_atomics['txv'] = len(tag_to_predict.split('-'))==2
                s0_atomics['txn'] = isinstance(tag_to_predict,ETag)
                s0_atomics['txdelta'] = delta_func(tag_to_predict,s0_atomics['form'])
            else:
                s0_atomics['txv'] = NOT_ASSIGNED
                s0_atomics['txn'] = NOT_ASSIGNED
                s0_atomics['txdelta'] = NOT_ASSIGNED
                s0_atomics['eqfrmset'] = NOT_ASSIGNED
            s0_atomics['isleaf'] = len(self.A.nodes[self.idx].children) == 0
        else:
            s0_atomics['txv'] = NOT_APPLY
            s0_atomics['txn'] = NOT_APPLY
            s0_atomics['txdelta'] = NOT_APPLY
            s0_atomics['eqfrmset'] = NOT_APPLY
            s0_atomics['isleaf'] = NOT_APPLY
        
        s0_args = None
        s0_prds = None
        if isinstance(self.idx,int) and GraphState.sent[self.idx].get('args',{}):
            s0_args = GraphState.sent[self.idx]['args']
        if isinstance(self.idx,int) and GraphState.sent[self.idx].get('pred',{}):
            s0_prds = GraphState.sent[self.idx]['pred']
        
        if self.cidx and self.cidx != START_ID:
            b0_atomics = GraphState.sent[self.cidx].copy() if isinstance(self.cidx,int) else ABT_TOKEN #GraphState.abt_tokens[self.cidx]
            b0_brown_repr = BROWN_CLUSTER[b0_atomics['form']]
            b0_atomics['brown4'] = b0_brown_repr[:4] if len(b0_brown_repr) > 3 else b0_brown_repr
            b0_atomics['brown6'] = b0_brown_repr[:6] if len(b0_brown_repr) > 5 else b0_brown_repr
            b0_atomics['brown8'] = b0_brown_repr[:8] if len(b0_brown_repr) > 7 else b0_brown_repr
            b0_atomics['brown10'] = b0_brown_repr[:10] if len(b0_brown_repr) > 9 else b0_brown_repr
            b0_atomics['brown20'] = b0_brown_repr[:20] if len(b0_brown_repr) > 19 else b0_brown_repr
            b0_atomics['concept'] = self.A.nodes[self.cidx].tag
            bprs2,bprs1,bp1,blsb,brsb,br2sb = self.get_node_context(self.cidx)
            b0_atomics['prs1']=bprs1
            b0_atomics['prs2']=bprs2
            b0_atomics['p1']=bp1
            b0_atomics['lsb']=blsb
            b0_atomics['rsb']=brsb
            b0_atomics['r2sb']=br2sb
            b0_atomics['nswp']=self.A.nodes[self.cidx].num_swap
            b0_atomics['reph']=sorted([GraphState.sent[rp]['form'] if isinstance(rp,int) else ABT_FORM for rp in self.A.nodes[self.cidx].rep_parent])
            b0_atomics['len']=self.A.nodes[self.cidx].end - self.A.nodes[self.cidx].start if isinstance(self.cidx,int) else NOT_ASSIGNED
            b0_atomics['dch']=sorted([GraphState.sent[j]['form'].lower() if isinstance(j,int) else ABT_FORM for j in self.A.nodes[self.cidx].del_child])
            b0_atomics['eqne']=(s0_atomics['ne']==b0_atomics['ne'] and b0_atomics['ne'] in PRE_MERGE_NETAG)
            b0_atomics['isne']=b0_atomics['ne'] in PRE_MERGE_NETAG
            b0_atomics['hastrace'] = len(self.A.nodes[self.cidx].incoming_traces) > 0

            # prop feature
            b0_atomics['isarg']=self.cidx in s0_args if s0_args else NOT_ASSIGNED
            b0_atomics['arglabel']=s0_args[self.cidx] if b0_atomics['isarg'] else NOT_ASSIGNED

            b0_atomics['isprd']=self.cidx in s0_prds if s0_prds else NOT_ASSIGNED
            b0_atomics['prdlabel']=s0_prds[self.cidx] if b0_atomics['isprd'] else NOT_ASSIGNED
            
            if isinstance(self.cidx,int) and isinstance(self.idx,int):
                path,direction = GraphState.deptree.get_path(self.cidx,self.idx)
                if self.A.nodes[self.idx].end - self.A.nodes[self.idx].start > 1:
                    path_pos_str = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1] if i not in range(self.A.nodes[self.idx].start,self.A.nodes[self.idx].end)]
                    path_x_str_pp = [('X','X') if not isprep(GraphState.sent[i]) else GraphState.sent[i]['form'] for i in path[1:-1] if i not in range(self.A.nodes[self.idx].start,self.A.nodes[self.idx].end)]
                else:
                    path_pos_str = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1]]
                    path_x_str_pp = [('X','X') if not isprep(GraphState.sent[i]) else GraphState.sent[i]['form']  for i in path[1:-1]]
                path_pos_str.insert(0,GraphState.sent[path[0]]['rel'])
                path_pos_str.append(GraphState.sent[path[-1]]['rel'])

                path_x_str_pp.insert(0,GraphState.sent[path[0]]['rel'])
                path_x_str_pp.append(GraphState.sent[path[-1]]['rel'])

                b0_atomics['pathp'] = path_pos_str
                b0_atomics['pathprep'] = path_x_str_pp
                b0_atomics['pathpwd'] = str(path_pos_str) + direction
                b0_atomics['pathprepwd'] = str(path_x_str_pp) + direction
            else:
                b0_atomics['pathp'] = EMPTY
                b0_atomics['pathprep'] = EMPTY
                b0_atomics['pathpwd'] = EMPTY
                b0_atomics['pathprepwd'] = EMPTY
                
            b0_atomics['apathx'] = EMPTY
            b0_atomics['apathp'] = EMPTY
            b0_atomics['apathprep'] = EMPTY
            b0_atomics['apathxwd'] = EMPTY
            b0_atomics['apathpwd'] = EMPTY
            b0_atomics['apathprepwd'] = EMPTY
        else:
            b0_atomics = EMPTY
        
            
        if action['type'] in [REATTACH,REENTRANCE]:
            #child_to_add = action['child_to_add']
            if action['type'] == REATTACH:
                parent_to_attach = action['parent_to_attach']
            else:
                parent_to_attach = action['parent_to_add']
            if parent_to_attach is not None:
                a0_atomics = GraphState.sent[parent_to_attach].copy() if isinstance(parent_to_attach,int) else ABT_TOKEN #GraphState.abt_tokens[parent_to_attach]
                a0_brown_repr = BROWN_CLUSTER[a0_atomics['form']]
                a0_atomics['brown4'] = a0_brown_repr[:4] if len(a0_brown_repr) > 3 else a0_brown_repr
                a0_atomics['brown6'] = a0_brown_repr[:6] if len(a0_brown_repr) > 5 else a0_brown_repr
                a0_atomics['brown8'] = a0_brown_repr[:8] if len(a0_brown_repr) > 7 else a0_brown_repr
                a0_atomics['brown10'] = a0_brown_repr[:10] if len(a0_brown_repr) > 9 else a0_brown_repr
                a0_atomics['brown20'] = a0_brown_repr[:20] if len(a0_brown_repr) > 19 else a0_brown_repr
                a0_atomics['concept'] = self.A.nodes[parent_to_attach].tag
                aprs2,aprs1,ap1,alsb,arsb,ar2sb = self.get_node_context(parent_to_attach)
                
                a0_atomics['p1']=ap1
                a0_atomics['lsb']=alsb
                a0_atomics['rsb']=arsb
                a0_atomics['r2sb']=ar2sb
                a0_atomics['nswp']=self.A.nodes[parent_to_attach].num_swap
                a0_atomics['isne']=a0_atomics['ne'] is not 'O'


                itr = list(self.A.nodes[self.cidx].incoming_traces)
                tr = [t for r,t in itr]
                a0_atomics['istrace'] = parent_to_attach in tr if len(tr) > 0 else EMPTY
                a0_atomics['rtr'] = itr[tr.index(parent_to_attach)][0] if parent_to_attach in tr else EMPTY
                a0_atomics['hasnsubj'] = b0_atomics['rel'] in set(GraphState.sent[c]['rel'] for c in self.A.nodes[parent_to_attach].children if isinstance(c,int))
                #a0_atomics['iscycle'] = parent_to_attach in self.A.nodes[self.cidx].children or parent_to_attach in self.A.nodes[self.cidx].parents

                # prop feature
                b0_prds = None
                b0_args = None
                if isinstance(self.cidx,int) and GraphState.sent[self.cidx].get('pred',{}):
                    b0_prds = GraphState.sent[self.cidx]['pred']
                if isinstance(self.cidx,int) and GraphState.sent[self.cidx].get('args',{}):
                    b0_args = GraphState.sent[self.cidx]['args']

                a0_atomics['isprd']=parent_to_attach in b0_prds if b0_prds else NOT_ASSIGNED
                a0_atomics['prdlabel']=b0_prds[parent_to_attach] if a0_atomics['isprd'] else NOT_ASSIGNED

                a0_atomics['isarg']=parent_to_attach in b0_args if b0_args else NOT_ASSIGNED
                a0_atomics['arglabel']=b0_args[parent_to_attach] if a0_atomics['isarg'] else NOT_ASSIGNED
                
                if isinstance(self.cidx,int) and isinstance(parent_to_attach,int):
                    path,direction = GraphState.deptree.get_path(self.cidx,parent_to_attach)
                #path_x_str=[(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1]]
                    if self.A.nodes[parent_to_attach].end - self.A.nodes[parent_to_attach].start > 1:                
                        apath_x_str = [('X','X') for i in path[1:-1] if i not in range(self.A.nodes[parent_to_attach].start,self.A.nodes[parent_to_attach].end)]
                        apath_pos_str = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1] if i not in range(self.A.nodes[parent_to_attach].start,self.A.nodes[parent_to_attach].end)]
                        apath_pos_str_pp = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) if not isprep(GraphState.sent[i]) else GraphState.sent[i]['form'] for i in path[1:-1] if i not in range(self.A.nodes[parent_to_attach].start,self.A.nodes[parent_to_attach].end)]
                    else:
                        apath_x_str = [('X','X') for i in path[1:-1]]
                        apath_pos_str = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1]]
                        apath_pos_str_pp = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) if not isprep(GraphState.sent[i]) else GraphState.sent[i]['form'] for i in path[1:-1]]
                    apath_x_str.insert(0,GraphState.sent[path[0]]['rel'])
                    apath_x_str.append(GraphState.sent[path[-1]]['rel'])            

                    apath_pos_str.insert(0,GraphState.sent[path[0]]['rel'])
                    apath_pos_str.append(GraphState.sent[path[-1]]['rel'])

                    apath_pos_str_pp.insert(0,GraphState.sent[path[0]]['rel'])
                    apath_pos_str_pp.append(GraphState.sent[path[-1]]['rel'])            

            #path_label_str = [GraphState.sent[i]['rel'] for i in path] # dependency label
            #path_lemma_str.insert(0,GraphState.sent[path[0]]['rel'])
            #path_lemma_str.append(GraphState.sent[path[-1]]['rel'])
                    b0_atomics['apathx'] = apath_x_str
                    b0_atomics['apathp'] = apath_pos_str
                    b0_atomics['apathprep'] = apath_pos_str_pp
                    b0_atomics['apathxwd'] = str(apath_x_str) + direction
                    b0_atomics['apathpwd'] = str(apath_pos_str) + direction
                    b0_atomics['apathprepwd'] = str(apath_pos_str_pp) + direction
            #a0_atomics['pathl'] = path_label_str
                else:
                    b0_atomics['pathp'] = EMPTY
                    b0_atomics['pathprep'] = EMPTY
                    b0_atomics['pathpwd'] = EMPTY
                    b0_atomics['pathprepwd'] = EMPTY
                    b0_atomics['apathx'] = EMPTY
                    b0_atomics['apathp'] = EMPTY
                    b0_atomics['apathprep'] = EMPTY
                    b0_atomics['apathxwd'] = EMPTY
                    b0_atomics['apathpwd'] = EMPTY
                    b0_atomics['apathprepwd'] = EMPTY

            else:
                a0_atomics = EMPTY
        else:
            a0_atomics = EMPTY
            #a0_atomics = s0_atomics

        '''
        if action['type'] == REENTRANCE:
            parent_to_add = action['parent_to_add']
            itr = list(self.A.nodes[self.cidx].incoming_traces)
            tr = [t for r,t in itr]
            a0_atomics['istrace'] = parent_to_add in tr if len(tr) > 0 else EMPTY
            #a0_atomics['rtr'] = itr[tr.index(parent_to_add)][0] if parent_to_add in tr else EMPTY
        else:
            a0_atomics = EMPTY
        '''
            
        if self.cidx == START_ID:
            s0_atomics['nech'] = len(set(GraphState.sent[j]['ne'] if isinstance(j,int) else ABT_NE for j in self.A.nodes[self.idx].children) & INFER_NETAG) > 0 
            s0_atomics['isnom'] = s0_atomics['lemma'].lower() in NOMLIST            
            s0_atomics['concept']=self.A.nodes[self.idx].tag
            if self.A.nodes[self.idx].children: 
                c1 = self.A.nodes[self.idx].children[0]
                s0_atomics['c1lemma'] = GraphState.sent[c1]['lemma'].lower() if isinstance(c1,int) else ABT_LEMMA
                s0_atomics['c1dl'] = GraphState.sent[c1]['rel'] if isinstance(c1,int) else ABT_LEMMA
            else:
                s0_atomics['c1lemma'] = EMPTY
                s0_atomics['c1dl'] = EMPTY
        else:
            s0_atomics['c1lemma'] = NOT_APPLY#EMPTY
            s0_atomics['concept'] = NOT_APPLY#EMPTY
            s0_atomics['nech'] = NOT_APPLY#EMPTY
            s0_atomics['isnom'] = NOT_APPLY#EMPTY
            s0_atomics['c1dl'] = NOT_APPLY#EMPTY

        '''
        if action['type'] == REENTRANCE and 'parent_to_add' in action: # reattach
            #child_to_add = action['child_to_add']
            parent_to_add = action['parent_to_add']
            r0_atomics = GraphState.sent[parent_to_add]
            rprs2,rprs1,rp1,rlsb,rrsb,rr2sb = self.get_node_context(parent_to_add)
            r0_atomics['p1']=rp1
            r0_atomics['lsb']=rlsb
            r0_atomics['rsb']=rrsb
            r0_atomics['r2sb']=rr2sb
            r0_atomics['nswp']=self.A.nodes[parent_to_add].num_swap
            r0_atomics['isne']=r0_atomics['ne'] is not 'O'
            #path,direction = self.A.get_path(self.cidx,parent_to_attach)
            path,direction = GraphState.deptree.get_path(self.cidx,parent_to_attach)
            #path_x_str=[(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1]]
            if self.A.nodes[parent_to_attach].end - self.A.nodes[parent_to_attach].start > 1:                
                apath_x_str = [('X','X') for i in path[1:-1] if i not in range(self.A.nodes[parent_to_attach].start,self.A.nodes[parent_to_attach].end)]
                apath_pos_str = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1] if i not in range(self.A.nodes[parent_to_attach].start,self.A.nodes[parent_to_attach].end)]
                apath_pos_str_pp = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) if not isprep(GraphState.sent[i]) else GraphState.sent[i]['form'] for i in path[1:-1] if i not in range(self.A.nodes[parent_to_attach].start,self.A.nodes[parent_to_attach].end)]
            else:
                apath_x_str = [('X','X') for i in path[1:-1]]
                apath_pos_str = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) for i in path[1:-1]]
                apath_pos_str_pp = [(GraphState.sent[i]['pos'],GraphState.sent[i]['rel']) if not isprep(GraphState.sent[i]) else GraphState.sent[i]['form'] for i in path[1:-1]]
            apath_x_str.insert(0,GraphState.sent[path[0]]['rel'])
            apath_x_str.append(GraphState.sent[path[-1]]['rel'])            

            apath_pos_str.insert(0,GraphState.sent[path[0]]['rel'])
            apath_pos_str.append(GraphState.sent[path[-1]]['rel'])

            apath_pos_str_pp.insert(0,GraphState.sent[path[0]]['rel'])
            apath_pos_str_pp.append(GraphState.sent[path[-1]]['rel'])            

            #path_label_str = [GraphState.sent[i]['rel'] for i in path] # dependency label
            #path_lemma_str.insert(0,GraphState.sent[path[0]]['rel'])
            #path_lemma_str.append(GraphState.sent[path[-1]]['rel'])
            b0_atomics['apathx'] = apath_x_str
            b0_atomics['apathp'] = apath_pos_str
            b0_atomics['apathprep'] = apath_pos_str_pp
            b0_atomics['apathxwd'] = str(apath_x_str) + direction
            b0_atomics['apathpwd'] = str(apath_pos_str) + direction
            b0_atomics['apathprepwd'] = str(apath_pos_str_pp) + direction
            #a0_atomics['pathl'] = path_label_str
        else:
            a0_atomics = EMPTY
        '''
        
        return (s0_atomics,b0_atomics,a0_atomics)
        
    def get_gold_edge_graph(self):
        gold_edge_graph = copy.deepcopy(self.A)
        parsed_tuples = gold_edge_graph.tuples()
        gold_tuples = self.gold_graph.tuples()
        
        for t_tuple in parsed_tuples:            
            if t_tuple in gold_tuples:            
                gold_arc_label = self.gold_graph.get_edge_label(t_tuple[0],t_tuple[1])
                gold_edge_graph.set_edge_label(t_tuple[0],t_tuple[1],gold_arc_label)

        return gold_edge_graph

    def get_gold_tag_graph(self):
        gold_tag_graph = copy.deepcopy(self.A)
        for nid in gold_tag_graph.nodes.keys()[:]:
            if nid in self.gold_graph.nodes:
                gold_tag_label = self.gold_graph.get_node_tag(nid)
                gold_tag_graph.set_node_tag(nid,gold_tag_label)
        return gold_tag_graph

    def get_gold_label_graph(self):
        gold_label_graph = copy.deepcopy(self.A)
        parsed_tuples = gold_label_graph.tuples()
        gold_tuples = self.gold_graph.tuples()
        for t_tuple in parsed_tuples:
            if t_tuple in gold_tuples:
                gold_arc_label = self.gold_graph.get_edge_label(t_tuple[0],t_tuple[1])
                gold_label_graph.set_edge_label(t_tuple[0],t_tuple[1],gold_arc_label)
                gold_tag_label1 = self.gold_graph.get_node_tag(t_tuple[0])
                gold_label_graph.set_node_tag(t_tuple[0],gold_tag_label1)
                gold_tag_label2 = self.gold_graph.get_node_tag(t_tuple[1])
                gold_label_graph.set_node_tag(t_tuple[1],gold_tag_label2)
        return gold_label_graph

    def evaluate(self):
        num_correct_arcs = .0
        num_correct_labeled_arcs = .0

        parsed_tuples = self.A.tuples()
        if self.verbose > 1:
            print >> sys.stderr, 'Parsed tuples:'+str(parsed_tuples) 
        num_parsed_arcs = len(parsed_tuples)
        gold_tuples = self.gold_graph.tuples()
        num_gold_arcs = len(gold_tuples)

        num_correct_tags = .0
        num_parsed_tags = .0
        num_gold_tags = .0
        visited_nodes = set()
        for t_tuple in parsed_tuples:
            p,c = t_tuple
            p_p,c_p = p,c
            if p in self.A.abt_node_table: p = self.A.abt_node_table[p]
            if c in self.A.abt_node_table: c = self.A.abt_node_table[c]
            if p_p not in visited_nodes:
                visited_nodes.add(p_p)
                p_tag = self.A.get_node_tag(p_p)
                if p in self.gold_graph.nodes:
                    g_p_tag = self.gold_graph.get_node_tag(p)
                    if p_tag == g_p_tag:# and not (isinstance(g_p_tag,(ETag,ConstTag)) or re.match('\w+-\d+',g_p_tag)): #and isinstance(g_p_tag,(ETag,ConstTag)):
                        num_correct_tags += 1.0
                    else:
                        self.A.nodes_error_table[p_p]=NODE_TYPE_ERROR
                else:
                    self.A.nodes_error_table[p_p]=NODE_MATCH_ERROR
                #    if p_tag == NULL_TAG:
                #        num_correct_tags += 1.0
            if c_p not in visited_nodes:
                visited_nodes.add(c_p)
                c_tag = self.A.get_node_tag(c_p)
                if c in self.gold_graph.nodes:
                    g_c_tag = self.gold_graph.get_node_tag(c)
                    if c_tag == g_c_tag:# and not (isinstance(g_c_tag,(ETag,ConstTag)) or re.match('\w+-\d+',g_c_tag)): #and isinstance(g_c_tag,(ETag,ConstTag)):
                        num_correct_tags += 1.0
                    else:
                        self.A.nodes_error_table[c_p]=NODE_TYPE_ERROR
                else:
                    self.A.nodes_error_table[c_p]=NODE_MATCH_ERROR
                #else:
                #    if c_tag == NULL_TAG:
                #        num_correct_tags += 1.0
                    
            if (p,c) in gold_tuples:
                num_correct_arcs += 1.0
                parsed_arc_label = self.A.get_edge_label(p_p,c_p)
                gold_arc_label = self.gold_graph.get_edge_label(p,c)
                if parsed_arc_label == gold_arc_label:
                    num_correct_labeled_arcs += 1.0
                else:
                    self.A.edges_error_table[(p_p,c_p)]=EDGE_TYPE_ERROR
            else:
                self.A.edges_error_table[(p_p,c_p)]=EDGE_MATCH_ERROR
                    
        #num_parsed_tags = len([i for i in visited_nodes if re.match('\w+-\d+',self.A.get_node_tag(i))])
        #num_gold_tags = len([j for j in self.gold_graph.nodes if re.match('\w+-\d+',self.gold_graph.get_node_tag(j))])
        #num_parsed_tags = len([i for i in visited_nodes if isinstance(self.A.get_node_tag(i),(ETag,ConstTag))])
        #num_gold_tags = len([j for j in self.gold_graph.nodes if isinstance(self.gold_graph.get_node_tag(j),(ETag,ConstTag))])
        #num_parsed_tags = len([i for i in visited_nodes if not (isinstance(self.A.get_node_tag(i),(ETag,ConstTag)) or re.match('\w+-\d+',self.A.get_node_tag(i)))])
        #num_gold_tags = len([j for j in self.gold_graph.nodes if not (isinstance(self.gold_graph.get_node_tag(j),(ETag,ConstTag)) or re.match('\w+-\d+',self.gold_graph.get_node_tag(j)))])
        num_parsed_tags = len(visited_nodes)
        num_gold_tags = len(self.gold_graph.nodes)
        return num_correct_labeled_arcs,num_correct_arcs,num_parsed_arcs,num_gold_arcs,num_correct_tags,num_parsed_tags,num_gold_tags
    '''
    def evaluate_actions(self,gold_state):
        gold_act_seq = gold_state.action_history
        parsed_act_seq = self.action_history
        confusion_matrix = np.zeros(shape=(len(GraphState.action_table),len(GraphState.action_table)))
        edge_label_count = defaultdict(float)
        # chop out the longer one
        common_step = len(gold_act_seq) if len(gold_act_seq) <= len(parsed_act_seq) else len(parsed_act_seq)
        for i in range(common_step):
            g_act = gold_act_seq[i]
            p_act = parsed_act_seq[i]

            confusion_matrix[g_act['type'],p_act['type']]+=1
            if g_act['type'] == p_act['type'] and g_act['type'] in ACTION_WITH_EDGE:
                if g_act == p_act:
                    edge_label_count[g_act['type']]+=1.0
        #for j in range(confusion_matrix.shape[0]):
        #    if j in ACTION_WITH_EDGE:
        #        confusion_matrix[j,j] = edge_label_count[j]/confusion_matrix[j,j] if confusion_matrix[j,j] != 0.0 else 0.0

        return confusion_matrix
    '''
        
    def get_score(self,act_type,feature,train=True): 
        act_idx = GraphState.model.class_codebook.get_index(act_type)       
        #if GraphState.model.weight[act_idx].shape[0] <= GraphState.model.feature_codebook[act_idx].size():
        #    GraphState.model.reshape_weight(act_idx)        
        weight = GraphState.model.weight[act_idx] if train else GraphState.model.avg_weight[act_idx]
        feat_idx = map(GraphState.model.feature_codebook[act_idx].get_index,feature)
        return np.sum(weight[ [i for i in feat_idx if i is not None] ],axis = 0)
        
    def make_feat(self,action):
        feat = GraphState.model.feats_generator(self,action)
        return feat
            
    def get_current_node(self):
        return self.A.nodes[self.idx]

    def get_current_child(self):
        if self.cidx and self.cidx in self.A.nodes:
            return self.A.nodes[self.cidx]
        else:
            return None

    def apply(self,action):
        action_type = action['type']
        other_params = dict([(k,v) for k,v in action.items() if k!='type' and v is not None])
        self.action_history.append(action)
        return getattr(self,GraphState.action_table[action_type])(**other_params)
        

    def next1(self, edge_label=None):
        newstate = self.pcopy()
        if edge_label and edge_label is not START_EDGE:newstate.A.set_edge_label(newstate.idx,newstate.cidx,edge_label)
        newstate.beta.pop()            
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(NEXT1)
            
        return newstate

    def next2(self, tag=None):
        newstate = self.pcopy()
        if tag: newstate.A.set_node_tag(newstate.idx,tag)
        newstate.sigma.pop()
        newstate.idx = newstate.sigma.top()
        newstate.beta = Buffer(newstate.A.nodes[newstate.idx].children) if newstate.idx != -1 else None
        if newstate.beta is not None: newstate.beta.push(START_ID)
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(NEXT2)
        
        return newstate

    def delete_node(self):
        newstate = self.pcopy()
        newstate.A.remove_node(newstate.idx,RECORD=True)
        newstate.sigma.pop()
        newstate.idx = newstate.sigma.top()        
        newstate.beta = Buffer(newstate.A.nodes[newstate.idx].children) if newstate.idx != -1 else None
        if newstate.beta is not None: newstate.beta.push(START_ID)
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(DELETENODE)
            
        return newstate

    def infer(self, tag):
        '''
        infer abstract node on core noun
        '''
        newstate = self.pcopy()
        abt_node_index = newstate.A.new_abt_node(newstate.idx,tag)
        
        # add the atomic info from its core noun
        #abt_atomics = {}
        #abt_atomics['id'] = abt_node_index
        #abt_atomics['form'] = ABT_FORM
        #abt_atomics['lemma'] = ABT_LEMMA
        #abt_atomics['pos'] = GraphState.sent[newstate.idx]['pos'] if isinstance(newstate.idx,int) else GraphState.abt_tokens[newstate.idx]['pos']
        #abt_atomics['ne'] = GraphState.sent[newstate.idx]['ne'] if isinstance(newstate.idx,int) else GraphState.abt_tokens[newstate.idx]['ne']
        #abt_atomics['rel'] = GraphState.sent[newstate.idx]['rel'] if isinstance(newstate.idx,int) else GraphState.abt_tokens[newstate.idx]['rel']
        #GraphState.abt_tokens[abt_node_index] = abt_atomics
        
        tmp = newstate.sigma.pop()
        newstate.sigma.push(abt_node_index)
        newstate.sigma.push(tmp)
        return newstate
    '''
    infer abstract node on edge pair: may cause feature inconsistency 
    def infer1(self):
        newstate = self.pcopy()
        abt_node_index = newstate.A.new_abt_node(newstate.idx)
        newstate.A.reattach_node(newstate.idx,newstate.cidx,abt_node_index,NULL_EDGE)
        tmp = newstate.sigma.pop()
        newstate.sigma.push(abt_node_index)
        newstate.sigma.push(tmp)
        newstate.beta.pop()
        newstate.beta.append(abt_node_index)
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        return newstate
    '''
    
    '''
    def delete_edge(self):
        newstate = self.pcopy()
        newstate.A.remove_edge(newstate.idx,newstate.cidx)
        #catm = self.atomics[newstate.cidx]
        #cparents = sorted(newstate.A.nodes[self.cidx].parents)
        #catm['blp1'] = GraphState.sent[cparents[0]] if cparents and cparents[0] < self.cidx else NOT_ASSIGNED
        newstate.beta.pop()
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(DELETEEDGE)

        return newstate
    '''
    
    def reattach(self,parent_to_attach=None,edge_label=None):
        newstate = self.pcopy()
        newstate.A.reattach_node(newstate.idx,newstate.cidx,parent_to_attach,edge_label)
        newstate.beta.pop()
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        return newstate
        
    def swap(self,edge_label):
        newstate = self.pcopy()        
        newstate.A.swap_head2(newstate.idx,newstate.cidx,newstate.sigma,edge_label)
        newstate._fix_prop_feature(newstate.idx,newstate.cidx)
        #newstate.idx = newstate.cidx
        tmp = newstate.sigma.pop()
        tmp1 = newstate.sigma.pop() if newstate.A.nodes[tmp].num_parent_infer > 0 else None
        if newstate.cidx not in newstate.sigma: newstate.sigma.push(newstate.cidx)
        if tmp1: newstate.sigma.push(tmp1)
        newstate.sigma.push(tmp)

        # TODO revisit
        #newstate.beta.pop()
        newstate.beta = Buffer([c for c in newstate.A.nodes[newstate.idx].children if c != newstate.cidx and c not in newstate.A.nodes[newstate.cidx].parents])
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(SWAP)

        return newstate
    '''
    def change_head(self,goldParent):
        newstate = self.pcopy()
        newstate.A.remove_edge(newstate.idx,newstate.cidx)
        newstate.A.add_edge(goldParent,newstate.cidx)
        newstate.A.relativePos(newstate.cidx,goldParent)
    '''

    def reentrance(self,parent_to_add,edge_label=None):
        newstate = self.pcopy()
        #delnodes = newstate.A.clear_up(parent_to_add,newstate.cidx)
        #for dn in delnodes:
        #    if dn in newstate.sigma:
        #        newstate.sigma.remove(dn)
        if edge_label:
            try:
                newstate.A.add_edge(parent_to_add,newstate.cidx,edge_label)
            except KeyError:
                import pdb
                pdb.set_trace()
        else:
            newstate.A.add_edge(parent_to_add,newstate.cidx)        
        return newstate
    
    def add_child(self,child_to_add,edge_label=None):
        newstate = self.pcopy()            
        if edge_label:
            newstate.A.add_edge(newstate.idx,child_to_add,edge_label)
        else:
            newstate.A.add_edge(newstate.idx,child_to_add)


        #hoffset,voffset = GraphState.deptree.relativePos(newstate.idx,node_to_add)
        #atype = GraphState.deptree.relativePos2(newstate.idx,child_to_add)
        #self.new_actions.add('add_child_('+str(hoffset)+')_('+str(voffset)+')_'+str(GraphState.sentID))
        #self.new_actions.add('add_child_%s_%s'%(atype,str(GraphState.sentID)))
        #newstate.action_history.append(ADDCHILD)
        return newstate


    def _fix_prop_feature(self,idx,cidx):
        '''update cidx's prop feature with idx's prop feature'''
        if isinstance(idx,int) and isinstance(cidx,int):
            ctok = GraphState.sent[cidx]
            tok = GraphState.sent[idx]
            ctok['pred'] = ctok.get('pred',{})
            ctok['pred'].update(dict((k,v) for k,v in tok.get('pred',{}).items() if k!=cidx))
            for prd in tok.get('pred',{}).copy():
                if prd != cidx:
                    try:
                        tmp = GraphState.sent[prd]['args'].pop(idx)
                        GraphState.sent[idx]['pred'].pop(prd)
                    except KeyError:
                        import pdb
                        pdb.set_trace()                        
                    GraphState.sent[prd]['args'][cidx] = tmp
                    
                        
            ctok['args'] = ctok.get('args',{})
            ctok['args'].update(dict((k,v) for k,v in tok.get('args',{}).items() if k!=cidx))
            for arg in tok.get('args',{}).copy():
                if arg != cidx:
                    try:
                        atmp = GraphState.sent[arg]['pred'].pop(idx)
                        GraphState.sent[idx]['args'].pop(arg)
                    except KeyError:
                        import pdb
                        pdb.set_trace()
                    GraphState.sent[arg]['pred'][cidx] = atmp
                    
    def replace_head(self):
        """
        Use current child to replace current node
        """
        newstate = self.pcopy()
        newstate.beta = Buffer([c for c in newstate.A.nodes[newstate.idx].children if c != newstate.cidx and c not in newstate.A.nodes[newstate.cidx].parents])
        #for old_c in newstate.A.nodes[newstate.cidx].children: newstate.beta.push(old_c)
        newstate.A.replace_head(newstate.idx,newstate.cidx)
        newstate._fix_prop_feature(newstate.idx,newstate.cidx)
        if newstate.idx in newstate.sigma: newstate.sigma.remove(newstate.idx)
        if newstate.cidx in newstate.sigma: newstate.sigma.remove(newstate.cidx) # pushing cidx to top
        newstate.sigma.push(newstate.cidx)
        newstate.A.record_rep_head(newstate.cidx,newstate.idx)    
        newstate.idx = newstate.cidx
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(REPLACEHEAD)

        return newstate

    def merge(self):
        """
        merge nodes to form entity 
        """
        newstate = self.pcopy()
        tmp1 = newstate.idx
        tmp2 = newstate.cidx
        #try:
        newstate.A.merge_node(tmp1,tmp2)
        #except KeyError:
        #    import pdb
        #    pdb.set_trace()

        if tmp1 < tmp2:
            if tmp2 in newstate.sigma:
                newstate.sigma.remove(tmp2)
        else:
            if tmp2 in newstate.sigma: newstate.sigma.remove(tmp2) # pushing tmp2 to the top
            newstate.sigma.push(tmp2)
            if tmp1 in newstate.sigma: newstate.sigma.remove(tmp1)


        newstate.idx = tmp1 if tmp1 < tmp2 else tmp2
        newstate.cidx = tmp2 if tmp1 < tmp2 else tmp1
        GraphState.sent[newstate.idx]['rel'] = GraphState.sent[tmp1]['rel']
        newstate._fix_prop_feature(newstate.cidx,newstate.idx)
        #newstate.A.merge_node(newstate.idx,newstate.cidx)
        newstate.beta = Buffer(newstate.A.nodes[newstate.idx].children[:])
        newstate.cidx = newstate.beta.top() if newstate.beta else None
        #newstate.action_history.append(MERGE)

        return newstate

    @staticmethod
    def get_parsed_amr(span_graph):

        def unpack_node(node,amr,variable):
            node_id = node.start
            node_tag = node.tag
            #if node.tag is None:
            #    import pdb
            #    pdb.set_trace()
            core_var = None
            tokens_in_span = GraphState.sent[node.start:node.end] if isinstance(node_id,int) else node.words
            if isinstance(node_tag,ETag):
                foo = amr[variable]
                pre_abs_id = None
                rel = None
                for i,abs_tag in enumerate(node_tag.split('+')):
                    if i == 0: # node already initialized
                        if '@' in abs_tag: abs_tag,rel = abs_tag.split('@')
                        amr.node_to_concepts[variable] = abs_tag
                        pre_abs_id = variable
                    elif abs_tag == '-': # negation
                        abs_id = Polarity(abs_tag)
                        foo = amr[abs_id]
                        rel = 'polarity'
                        amr._add_triple(pre_abs_id,rel,abs_id)
                        pre_abs_id = abs_id
                    else:
                        abs_id = abs_tag[0].lower()
                        j = 0
                        while abs_id in amr:
                            j+=1
                            abs_id = abs_id[0]+str(j)
                            
                        foo = amr[abs_id]
                        amr._add_triple(pre_abs_id,rel,abs_id)
                        if '@' in abs_tag:
                            abs_tag,rel = abs_tag.split('@')
                        else:
                            rel = None
                        amr.node_to_concepts[abs_id] = abs_tag
                        #rel = abs_tag

                        pre_abs_id = abs_id
                

                last_abs_id = pre_abs_id
                last_abs_tag = abs_tag
                if last_abs_tag == '-':
                    return variable,core_var
                
                rel_in_span = 'op' if rel is None else rel
                for i,tok in enumerate(tokens_in_span):
                    foo = amr[tok['form']]
                    if last_abs_tag == 'name':
                        amr._add_triple(last_abs_id,'op'+str(i+1),StrLiteral(tok['form']))
                    elif last_abs_tag == 'date-entity':
                        date_pattern = [
                            ('d1','^({0}{0}{0}{0})(\-{0}{0})?(\-{0}{0})?$'.format('[0-9]')),
                            ('d2','^({0}{0})({0}{0})({0}{0})$'.format('[0-9]'))
                        ]
                        date_rule = '|'.join('(?P<%s>%s)'%(p,d) for p,d in date_pattern)
                        m = re.match(date_rule,tok['form'])
                        if m:
                            year,month,day = None,None,None
                            date_type = m.lastgroup
                            
                            if date_type == 'd1':
                                year = m.group(2)
                                if m.group(3) is not None: month = str(int(m.group(3)[1:]))
                                if m.group(4) is not None: day = str(int(m.group(4)[1:]))
                            elif date_type == 'd2':
                                year = '20'+m.group(6)
                                month = str(int(m.group(7)))
                                day = str(int(m.group(8)))
                            else:
                                #raise ValueError('undefined date pattern')
                                pass

                            foo = amr[year]
                            amr._add_triple(last_abs_id,'year',Quantity(year))
                            if month and month != '0':
                                foo = amr[month]
                                amr._add_triple(last_abs_id,'month',Quantity(month))
                            if day and day != '0':
                                foo = amr[day]
                                amr._add_triple(last_abs_id,'day',Quantity(day))
                    elif last_abs_tag.endswith('-quantity'):
                        new_id = tok['form'][0].lower()
                        j = 0
                        while new_id in amr:
                            j+=1
                            new_id = new_id[0]+str(j)
                    
                        foo = amr[new_id]
                        amr.node_to_concepts[new_id] = tok['form']
                        amr._add_triple(last_abs_id,'unit',new_id)
                    elif last_abs_tag == 'have-org-role-91':
                        new_id = tok['lemma'][0].lower()
                        j = 0
                        while new_id in amr:
                            j+=1
                            new_id = new_id[0]+str(j)

                        foo = amr[new_id]
                        core_var = new_id
                        amr.node_to_concepts[new_id] = tok['lemma'].lower()
                        amr._add_triple(last_abs_id,rel_in_span,new_id)

                    else:
                        if re.match('[0-9\-]+',tok['form']):
                            amr._add_triple(last_abs_id,rel_in_span,Quantity(tok['form']))
                        else:
                            new_id = tok['lemma'][0].lower()
                            j = 0
                            while new_id in amr:
                                j+=1
                                new_id = new_id[0]+str(j)

                            foo = amr[new_id]
                            amr.node_to_concepts[new_id] = tok['lemma'].lower()
                            amr._add_triple(last_abs_id,rel_in_span,new_id)
            elif isinstance(node_tag,ConstTag):
                foo = amr[node_tag]
                variable = node_tag
            else:
                if r'/' in node_tag:
                    #import pdb
                    #pdb.set_trace()
                    variable = StrLiteral(node_tag)
                    foo = amr[variable]
                else:
                    foo = amr[variable]
                    amr.node_to_concepts[variable] = node_tag # concept tag
                
            return variable,core_var
        
        amr = AMR()
        span_graph.flipConst()
        node_prefix = 'x'
        cpvar_cache = {}
        
        for parent,child in span_graph.tuples(): 
            pvar = node_prefix+str(parent)
            cvar = node_prefix+str(child)


            try:
                if parent == 0:
                    if cvar not in amr:
                        cvar,ccvar = unpack_node(span_graph.nodes[child],amr,cvar)
                        cpvar_cache[cvar] = ccvar
                    if cvar not in amr.roots: amr.roots.append(cvar)
                else:
                    rel_label = span_graph.get_edge_label(parent,child)
                    if pvar not in amr:
                        pvar,cpvar = unpack_node(span_graph.nodes[parent],amr,pvar)
                        cpvar_cache[pvar]=cpvar
                    if cvar not in amr:
                        cvar,ccvar = unpack_node(span_graph.nodes[child],amr,cvar)
                        cpvar_cache[cvar]=ccvar
                    if cpvar_cache.get(pvar,None) and rel_label == 'mod':
                        amr._add_triple(cpvar_cache[pvar],rel_label,cvar)
                    else:
                        amr._add_triple(pvar,rel_label,cvar)
            except ValueError as e:
                print e
                #print span_graph.graphID
                
        if len(amr.roots) > 1:
            foo =  amr[FAKE_ROOT_VAR]
            amr.node_to_concepts[FAKE_ROOT_VAR] = FAKE_ROOT_CONCEPT
            for multi_root in amr.roots:
                amr._add_triple(FAKE_ROOT_VAR,FAKE_ROOT_EDGE,multi_root)
            amr.roots = [FAKE_ROOT_VAR]
        elif len(amr.roots) == 0 and len(amr.keys()) != 0:
            foo =  amr[FAKE_ROOT_VAR]
            amr.node_to_concepts[FAKE_ROOT_VAR] = FAKE_ROOT_CONCEPT
            for mlt_root in span_graph.get_multi_roots():
                mrvar = node_prefix + str(mlt_root)
                if mrvar in amr:
                    amr._add_triple(FAKE_ROOT_VAR,FAKE_ROOT_EDGE,mrvar)
            amr.roots=[FAKE_ROOT_VAR]
        elif len(amr.roots) == 1 and amr.roots[0] not in amr.node_to_concepts: # Const tag
            foo =  amr[FAKE_ROOT_VAR]
            amr.node_to_concepts[FAKE_ROOT_VAR] = FAKE_ROOT_CONCEPT
            amr._add_triple(FAKE_ROOT_VAR,FAKE_ROOT_EDGE,amr.roots[0])
            amr.roots = [FAKE_ROOT_VAR]
        elif len(amr.keys()) == 0:
            foo =  amr[FAKE_ROOT_VAR]
            amr.node_to_concepts[FAKE_ROOT_VAR] = FAKE_ROOT_CONCEPT
            for mlt_root in span_graph.get_multi_roots():
                mrvar = node_prefix + str(mlt_root)
                foo = amr[mrvar]
                amr.node_to_concepts[mrvar] = span_graph.nodes[mlt_root].tag
                amr._add_triple(FAKE_ROOT_VAR,FAKE_ROOT_EDGE,mrvar)
            amr.roots=[FAKE_ROOT_VAR]
                    
        else:
            pass
            
            
        return amr
                
        
    def print_config(self, column_len = 80):
        output = ''
        if self.cidx:
            if self.idx == START_ID:
                span_g = START_FORM
            else:
                span_g = ','.join(tok['form'] for tok in GraphState.sent[self.idx:self.A.nodes[self.idx].end]) if isinstance(self.idx,int) else ','.join(self.A.nodes[self.idx].words)
            if self.cidx == START_ID:
                span_d = START_FORM
            else:
                span_d = ','.join(tok['form'] for tok in GraphState.sent[self.cidx:self.A.nodes[self.cidx].end]) if isinstance(self.cidx,int) else ','.join(self.A.nodes[self.cidx].words)
            output += 'ID:%s %s\nParent:(%s-%s) Child:(%s-%s)'%(str(GraphState.sentID),self.text,\
                                                   span_g, self.idx, \
                                                   span_d, self.cidx)
        else:
            '''
            if self.action_history and self.action_history[-1] == ADDCHILD: # add child
                added_child_idx = self.A.nodes[self.idx].children[-1]
                output += 'ID:%s %s\nParent:(%s-%s) add child:(%s-%s)'%(str(GraphState.sentID),self.text,\
                                                           ','.join(tok['form'] for tok in GraphState.sent[self.idx:self.A.nodes[self.idx].end]), self.idx, \
                                                    ','.join(tok['form'] for tok in GraphState.sent[added_child_idx:self.A.nodes[added_child_idx].end]), added_child_idx)
            else:
            '''  
            if self.idx == START_ID:
                span_g = START_FORM
                output += 'ID:%s %s\nParent:(%s-%s) Children:%s'%(str(GraphState.sentID),self.text,\
                                                                      span_g, self.idx, 'None')
            else:  
                span_g = ','.join(tok['form'] for tok in GraphState.sent[self.idx:self.A.nodes[self.idx].end]) if isinstance(self.idx,int) else ','.join(self.A.nodes[self.idx].words)
                output += 'ID:%s %s\nParent:(%s-%s) Children:%s'%(str(GraphState.sentID),self.text,\
                                                                      span_g, self.idx, \
                                                                      ['('+','.join(tok['form'] for tok in GraphState.sent[c:self.A.nodes[c].end])+')' if isinstance(c,int) else '('+','.join(self.A.nodes[c].words)+')' for c in self.A.nodes[self.idx].children])

        output += '\n'
        parsed_tuples = self.A.tuples()
        ref_tuples = self.gold_graph.tuples()
        num_p = len(parsed_tuples)
        num_r = len(ref_tuples)
        tnum = num_r if num_r > num_p else num_p
        for i in range(tnum):
            strformat = '{0:<%s}|{1:<%s}' % (column_len,column_len)
            if i < num_p and i < num_r:
                g,d = parsed_tuples[i]
                gg,gd = ref_tuples[i]
                parsed_edge_label = self.A.get_edge_label(g,d) 
                gold_edge_label = self.gold_graph.get_edge_label(gg,gd)
                gold_span_gg = ','.join(tok['form'] for tok in GraphState.sent[gg:self.gold_graph.nodes[gg].end]) if isinstance(gg,int) else ','.join(self.gold_graph.nodes[gg].words)
                gold_span_gd = ','.join(tok['form'] for tok in GraphState.sent[gd:self.gold_graph.nodes[gd].end]) if isinstance(gd,int) else ','.join(self.gold_graph.nodes[gd].words)
                parsed_span_g = ','.join(tok['form'] for tok in GraphState.sent[g:self.A.nodes[g].end]) if isinstance(g,int) else ','.join(self.A.nodes[g].words)
                parsed_span_d = ','.join(tok['form'] for tok in GraphState.sent[d:self.A.nodes[d].end]) if isinstance(d,int) else ','.join(self.A.nodes[d].words)
                parsed_tag_g = self.A.get_node_tag(g)
                parsed_tag_d = self.A.get_node_tag(d)
                gold_tag_gg = self.gold_graph.get_node_tag(gg)
                gold_tag_gd = self.gold_graph.get_node_tag(gd)
                parsed_tuple_str = "(%s(%s-%s:%s),(%s-%s:%s))" % (parsed_edge_label, parsed_span_g, g, parsed_tag_g, parsed_span_d, d, parsed_tag_d)
                ref_tuple_str = "(%s(%s-%s:%s),(%s-%s:%s))" % (gold_edge_label, gold_span_gg, gg, gold_tag_gg, gold_span_gd, gd, gold_tag_gd)
                output += strformat.format(parsed_tuple_str,ref_tuple_str)
                output += '\n'
            elif i < num_p and i >= num_r:
                g,d = parsed_tuples[i]
                parsed_edge_label = self.A.get_edge_label(g,d)
                parsed_tag_g = self.A.get_node_tag(g)
                parsed_tag_d = self.A.get_node_tag(d)
                parsed_span_g = ','.join(tok['form'] for tok in GraphState.sent[g:self.A.nodes[g].end]) if isinstance(g,int) else ','.join(self.A.nodes[g].words)
                parsed_span_d = ','.join(tok['form'] for tok in GraphState.sent[d:self.A.nodes[d].end]) if isinstance(d,int) else ','.join(self.A.nodes[d].words)
                parsed_tuple_str = "(%s(%s-%s:%s),(%s-%s:%s))" % (parsed_edge_label, parsed_span_g, g, parsed_tag_g, parsed_span_d, d, parsed_tag_d)
                output += strformat.format(parsed_tuple_str,'*'*column_len)
                output += '\n'
            elif i >= num_p and i < num_r:
                gg,gd = ref_tuples[i]
                gold_edge_label = self.gold_graph.get_edge_label(gg,gd)
                gold_span_gg = ','.join(tok['form'] for tok in GraphState.sent[gg:self.gold_graph.nodes[gg].end]) if isinstance(gg,int) else ','.join(self.gold_graph.nodes[gg].words)
                gold_span_gd = ','.join(tok['form'] for tok in GraphState.sent[gd:self.gold_graph.nodes[gd].end]) if isinstance(gd,int) else ','.join(self.gold_graph.nodes[gd].words)
                gold_tag_gg = self.gold_graph.get_node_tag(gg)
                gold_tag_gd = self.gold_graph.get_node_tag(gd)
                ref_tuple_str = "(%s(%s-%s:%s),(%s-%s:%s))" % (gold_edge_label, gold_span_gg, gg, gold_tag_gg, gold_span_gd, gd, gold_tag_gd)
                output += strformat.format('*'*column_len,ref_tuple_str)
                output += '\n'
            else:
                pass

        return output


    def write_basic_amr(self,out,CONST_REL='ARG0'):
        '''
        this method takes the unlabeled edges produced by the parser and
        adds them with fake amr relation which is mapped from dependency tag set        
        '''
        CoNLLSent = GraphState.sent
        parsed_tuples = self.A.tuples()
        out.write(str(GraphState.sentID)+'\n')
        fake_amr_triples = []
        for g,d in parsed_tuples:
            gov = CoNLLSent[g]
            dep = CoNLLSent[d]
            if dep['head'] == gov['id']: # tuple also in dependency tree
                rel = get_fake_amr_relation_mapping(dep['rel']) if get_fake_amr_relation_mapping(dep['rel']) != 'NONE' else CONST_REL
                fake_amr_triples.append((rel,gov['lemma'],dep['lemma']))
            else:
                fake_amr_triples.append((CONST_REL,gov['lemma'],dep['lemma']))
            out.write(str(fake_amr_triples[-1])+'\n')
        return fake_amr_triples
