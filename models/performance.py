"""Price-reference ledger. Observed close signals never earn today's move."""
import numpy as np


def replay(target, close, cash_return, distribution=None, execution='same_close_reference',
           opening=None, extra_cost=0., band=.125):
    target=np.asarray(target,float);close=np.asarray(close,float);cash_return=np.asarray(cash_return,float)
    if target.shape!=close.shape or target.ndim!=2 or target.shape[1]!=6:
        raise ValueError('성과 장부의 비중·가격 형태가 다릅니다')
    if (not np.isfinite(close).all() or (close<=0).any() or not np.isfinite(target).all()
            or (target < -1e-12).any() or not np.allclose(target.sum(axis=1),1)
            or not np.isfinite(cash_return).all()):
        raise ValueError('성과 장부 입력 누락')
    if execution not in ['same_close_reference','next_close','next_open']:
        raise ValueError('지원하지 않는 성과 체결 기준')
    opening=close if opening is None else np.asarray(opening,float)
    if opening.shape!=close.shape or not np.isfinite(opening).all() or (opening<=0).any():
        raise ValueError('성과 시가 누락')
    distribution=np.zeros_like(close) if distribution is None else np.asarray(distribution,float)
    if distribution.shape!=close.shape or not np.isfinite(distribution).all():raise ValueError('분배금 입력 누락')
    n=len(target);nav=np.ones(n);trades=np.zeros(n,int);turn=np.zeros(n);fees=np.zeros(n)
    held=np.array([0.,0.,0.,1.,0.,0.]);value=1.;rate=np.full(6,.001+extra_cost);rate[3]=0
    goal=target[0].copy();pending=np.max(abs(goal-held))>=band

    def trade(goal,held,value,i):
        lo,hi=0.,1.
        for _ in range(55):
            k=(lo+hi)/2
            if k+np.dot(abs(k*goal-held),rate)>1:hi=k
            else:lo=k
        k=(lo+hi)/2;delta=abs(k*goal-held)
        trades[i]=1;turn[i]=delta[[0,1,2,4,5]].sum();fees[i]=np.dot(delta,rate)
        return goal.copy(),value*k

    for i in range(n):
        if i:
            g=opening[i]/close[i-1];g[3]=1+cash_return[i];g-=distribution[i]*.001
            mark=held*g;value*=mark.sum();held=mark/mark.sum()
            if execution=='next_open' and pending:held,value=trade(goal,held,value,i)
            g=close[i]/opening[i];g[3]=1
            mark=held*g;value*=mark.sum();held=mark/mark.sum()
            if execution=='next_close' and pending:held,value=trade(goal,held,value,i)
        if execution=='same_close_reference':
            if np.max(abs(target[i]-held))>=band:held,value=trade(target[i],held,value,i)
        # Today's signal can fill today only in explicit price-reference mode.
        goal=target[i].copy();pending=np.max(abs(goal-held))>=band
        nav[i]=value
    return nav,trades,turn,fees
