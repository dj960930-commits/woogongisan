import numpy as np
import pandas as pd
from tools.research_defense_36912 import scores, select, short_confirm

def test_weighted_simple_return_and_cash_compounding():
    ix=pd.bdate_range('2010-01-01',periods=260)
    p=pd.DataFrame({'BRK.B':100*1.002**np.arange(260),
                    'GLD':100*1.001**np.arange(260),'cash_return':.001},index=ix)
    s=scores(p,(4,3,2,1))
    expected=sum(w*((1.002**n-1)-(1.001**n-1)) for n,w in zip((63,126,189,252),(4,3,2,1)))/10
    np.testing.assert_allclose(s['BRK.B'].iloc[-1],expected)
    np.testing.assert_allclose(s.GLD.iloc[-1],0,atol=1e-12)
    assert s.iloc[251].isna().all()

def test_selection_warmup_ties_and_cash_gate_after_override():
    s=pd.DataFrame({'BRK.B':[np.nan,.2,-.1,.1], 'GLD':[.3,.2,-.2,-.1]})
    original=pd.Series(['BRK.B','GLD','GLD','BRK.B'])
    confirm=pd.DataFrame({'BRK.B':[False]*4,'GLD':[False,False,False,True]})
    assert select(s,original).tolist()==['BRK.B','GLD','BRK.B','BRK.B']
    assert select(s,original,confirm,True).tolist()==['BRK.B','GLD','CASH','CASH']

def test_short_confirmation_requires_three_completed_observations():
    ix=pd.bdate_range('2010-01-01',periods=40)
    p=pd.DataFrame({'BRK.B':100*1.01**np.arange(40),'GLD':100.},index=ix)
    c=short_confirm(p)
    assert not c['BRK.B'].iloc[:23].any()
    assert c['BRK.B'].iloc[23:].all()
    assert not c.GLD.any()
    pd.testing.assert_frame_equal(c.iloc[:30],short_confirm(p.iloc[:30]))
