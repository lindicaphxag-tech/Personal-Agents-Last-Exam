"""Sparse range-chmin index returning exactly the newly improved integer times."""
from dataclasses import dataclass
from math import inf

@dataclass(slots=True)
class Node:
    low: int | float = inf
    high: int | float = inf
    left: 'Node | None' = None
    right: 'Node | None' = None

class Coverage:
    def __init__(self, start: int, horizon: int):
        if type(start) is not int or type(horizon) is not int or start > horizon:
            raise ValueError('invalid domain')
        self.start, self.horizon = start, horizon
        self.root = Node()
        self.visits = 0

    def improve(self, lo: int, hi: int, distance: int):
        """Return maximal intervals where distance is strictly smaller, then update."""
        if any(type(x) is not int for x in (lo,hi,distance)) or not self.start <= lo <= hi <= self.horizon or distance < 0:
            raise ValueError('invalid update')
        out=[]
        def emit(a,b):
            if out and out[-1][1]+1 == a: out[-1]=(out[-1][0],b)
            else: out.append((a,b))
        def update(n,a,b):
            self.visits += 1
            if b<lo or a>hi or n.high<=distance:return
            if lo<=a and b<=hi and n.low>distance:
                n.low=n.high=distance;n.left=n.right=None;emit(a,b);return
            mid=(a+b)//2
            if n.left is None:
                n.left=Node(n.low,n.high);n.right=Node(n.low,n.high)
            update(n.left,a,mid);update(n.right,mid+1,b)
            n.low=min(n.left.low,n.right.low);n.high=max(n.left.high,n.right.high)
            if n.low==n.high:n.left=n.right=None
        update(self.root,self.start,self.horizon)
        return out
