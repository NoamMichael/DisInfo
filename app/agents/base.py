"""Base class for all pipeline agents."""

import time
from app.observe import obs


class Agent:
    name: str = "base"

    def __init__(self):
        self.result = None

    def log(self, message: str, **kw):
        obs.info(self.name, message, **kw)

    def run(self, **kwargs):
        obs.start(self.name)
        t0 = time.monotonic()
        try:
            self.result = self.execute(**kwargs)
            dur = (time.monotonic() - t0) * 1000
            obs.end(self.name, self.summary(), duration_ms=round(dur, 1))
            return self.result
        except Exception as e:
            obs.error(self.name, str(e))
            raise

    async def arun(self, **kwargs):
        obs.start(self.name)
        t0 = time.monotonic()
        try:
            self.result = await self.aexecute(**kwargs)
            dur = (time.monotonic() - t0) * 1000
            obs.end(self.name, self.summary(), duration_ms=round(dur, 1))
            return self.result
        except Exception as e:
            obs.error(self.name, str(e))
            raise

    def execute(self, **kwargs):
        raise NotImplementedError

    async def aexecute(self, **kwargs):
        raise NotImplementedError

    def summary(self) -> str:
        return f"{self.name} complete"
