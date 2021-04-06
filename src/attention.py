from functools import wraps, WRAPPER_ASSIGNMENTS
import threading
from typing import Optional, Union, List, Tuple
from collections.abc import Callable
from time import sleep
from datetime import timedelta, datetime
import asyncio

try:
    from schedule import Scheduler, Job
except ModuleNotFoundError:
    import pip
    pip.main(['install', 'schedule==1.0.0'])

class Attention(object):
    def __init__(self, max_workers: Optional[int] = 2):
        self._pool = []
    
    @staticmethod
    def schedule(
        interval: Union[None, timedelta] = None,
        standfor: Union[None, timedelta] = None,
        until: Union[None, datetime] = None,
        group: int = 0
    ):
        if not isinstance(interval, timedelta):
            raise TypeError(f':interval: argument should be an instance of <datetime.timedelta>, but {type(interval)} is detected with value: {interval}')
        if standfor and until:
            raise NotImplementedError(f':standfor: argument cannot appear with :until: argument')
        
        if standfor:
            if not isinstance(standfor, timedelta):
                raise TypeError(f':interval: argument should be an instance of <datetime.timedelta>, but {type(standfor)} is detected with value: {standfor}')
        if until:
            if not isinstance(until, datetime):
                raise TypeError(f':until: argument should be an instance of <datetime.datetime>, but {type(until)} is detected with value: {until}')
            standfor: timedelta = until - datetime.now()
        
        def label(method):
            setattr(method, 
                    '__schinterval__', 
                    {
                        'delta': interval.total_seconds(),
                        'standfor': standfor.total_seconds() if isinstance(standfor, timedelta) else 0
                    }
                )
            setattr(method, '__schgroup__', {'group': group})
            return method
        return label
    
    @staticmethod
    def trigger(meth_or_grp: Union[Callable, int, Tuple[int]]):
        if isinstance(meth_or_grp, int):
            def label(method):
                setattr(method, '__schtrigger__', {'group': (meth_or_grp)})
                setattr(method, '__trigger__', True)
                return method
            return label
        assert callable(meth_or_grp), f'{meth_or_grp.__name__} is not callable'
        setattr(meth_or_grp, '__trigger__', True)
        return meth_or_grp
    
    def __call__(self, Cls: Optional[type] = None) -> type:
        class Wrapped(Cls):
            def __init__(self, *args, **kwargs):
                sup_rslt = super().__init__(*args, **kwargs)
                assignments = filter(
                    lambda x: hasattr(Cls, x), WRAPPER_ASSIGNMENTS
                )
                for attr in assignments:
                    setattr(self, attr, getattr(Cls, attr))
                
                self._onschmethods: List[Callable] =\
                    [getattr(self, x) for x in dir(self) if \
                     hasattr(getattr(self, x), '__schinterval__')]
                
                self._triggers: List[Callable] =\
                    [getattr(self, x) for x in dir(self) if \
                     hasattr(getattr(self, x), '__trigger__')]
                
                self._schlock: threading.Lock = threading.Lock() # For Accessing scheduler jobs queue
                self._schback: Scheduler = Scheduler()

                # [Temporarily mechanism] Due to to many threads may be spawned, this mechanism may be re-implement by asyncio with one thread.
                self._schkillers = [
                    threading.Timer(
                        interval = getattr(x, '__schinterval__').get('standfor'),
                        function = self.unsubscribe,
                        args = [x]
                    ) for x in self._onschmethods if getattr(x, '__schinterval__').get('standfor')
                ]

                self._schrunner: threading.Thread = threading.Thread(
                    target = self._schmain,
                    daemon = True
                )
                
                self._schrunner.start()
                for killer in self._schkillers:
                    killer.daemon = True
                    killer.start()
                
                return sup_rslt
            
            def _schmain(self) -> None:
                for method in self._onschmethods:
                    meth_delta: Union[float, int] = method.__schinterval__.get('delta', 0)
                    if meth_delta > 0:
                        Job(
                            interval = meth_delta, 
                            scheduler = self._schback
                        ).seconds.do(method).tag(method.__name__)
                    else: pass
                while True:
                    with self._schlock:
                        self._schback.run_pending()
                    sleep(0.5)
            
            def unsubscribe(self, method: Union[None, str, Callable] = None) -> int:
                if not method:
                    with self._schlock:
                        self._schback.clear()
                    return 1
                if callable(method):
                    if not hasattr(self, method.__name__):
                        raise AttributeError(f'Object does not has the method {method.__name__}')
                    if not method == getattr(self, method.__name__):
                        raise UnboundLocalError(f'method is not bound by current instance {self}. Do you mis-pass the method of other instance to current instance?')
                    with self._schlock:
                        self._schback.clear(method.__name__)
                    return 1
                if type(method) == str:
                    if not hasattr(self, method):
                        raise AttributeError(f'Object does not has the method {method}')
                    with self._schlock:
                        self._schback.clear(method)
                    return 1
                return -1
            
            def resubscribe(self, method: Union[None, str, Callable] = None) -> int:
                if not method:
                    pass
                return -1

        return Wrapped

def InstanceKeeper(cls_):
    class WrapedCLS(cls_):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            assignments = filter(
                lambda x: hasattr(cls_, x), WRAPPER_ASSIGNMENTS
            )
            for attr in assignments:
                setattr(self, attr, getattr(cls_, attr))
            
            self._keepers = threading.Thread()
        
        def startkeeperjob(self, callable_: Callable, *args, **kwargs):
            if not callable(callable_):
                raise TypeError(f'The type of callable_: {type(callable_)} is not callable')

            if not hasattr(self, callable_.__name__):
                raise NameError(f'The current instance does not have the method name {callable_.__name__}.')
            
            _local_method = getattr(self, callable_.__name__)

            if not _local_method == callable_:
                raise UnboundLocalError(f':callable_: method can not be controlled by the instance.')
            
            threading.Thread(
                target = callable_,
                args = args,
                kwargs = kwargs,
                daemon = True
            ).start()

    return WrapedCLS