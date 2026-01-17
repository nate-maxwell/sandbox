"""
Primary state engine.

Herein is a "state machine"-like engine that acts as the primary global
coordinator between subsystems.

Systems can define exclusive concepts as engine lifetimes. Lifetimes are a graph
of states and conditions for valid edge traversal from one state to another.

Systems do not call each other; they operate over shared state and report
results. The engine is responsible for recording current state and managing
and signalling transitions to other states.
"""

# We do not label this as a State Machine because it is authoritative, reactive,
# concurrent, extensible, etc., all properties not commonly found in SMs or FSMs.
# This system is a state machine at rest, and an engine when running.


import enum
import uuid
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional
from typing import Union

import broker


FACT_VALUE = Union[str, bool, int, enum.Enum]


@dataclass(frozen=True, order=True)
class Edge(object):
    """An edge between two state nodes."""

    priority: int
    """How likely should this transition be taken should multiple be satisfied?"""

    source: str
    """Required state for the transition to start."""

    target: str
    """Where to transition to."""

    requires: dict[str, FACT_VALUE] = field(compare=False)
    """
    Predicate name → required value mapping.

    All required predicates must be satisfied for the transition to be
    eligible.
    """


@dataclass(frozen=True)
class TransitionBlocker(object):
    """Descriptor for why a transition was blocked. Generated on request."""

    transition: Edge
    """The associated transition."""

    missing: dict[str, FACT_VALUE]
    """Required predicate values not present in the current transition."""

    mismatched: dict[str, tuple[FACT_VALUE | None, FACT_VALUE]]
    """Current predicate values that do not match the required value."""


class LifetimeDefinition(object):
    """
    Declarative definition of a lifecycle state machine.

    A `Lifetime` describes *what transitions are possible* between states and
    *which predicates must be satisfied* for those transitions to occur.
    It contains no execution logic, timing, or side effects.

    The engine uses a `Lifetime` as a compiled transition map, while
    `LifetimeRun` records *what has happened so far* for a specific execution.
    """

    def __init__(
        self,
        name: str,
        states: set[str],
        initial: str,
        terminal: set[str],
        transitions: dict[str, set[str]],
        predicates: Optional[dict[tuple[str, str], dict[str, FACT_VALUE]]] = None,
    ) -> None:
        """
        Initialize a declarative lifecycle definition.

        Args:
            name (str):
                Human-readable identifier for this lifetime definition.
                Used for debugging, logging, and diagnostics.

            states (set[str]):
                Complete set of valid state names for this lifetime.

            initial (str):
                Name of the starting state. Must exist in `states`.

            terminal (set[str]):
                Set of states that represent completion. Once entered,
                the associated `LifetimeRun` will be marked finished.

            transitions (dict[str, set[str]):
                Mapping of source state → set of allowed target states.
                This defines the structural graph of the lifetime.

            predicates (dict[tuple[str, str], dict[str, FACT_VALUE]]):
                Optional mapping of (source, target) transition pairs to
                required predicate values. All predicates for a transition
                must be satisfied for it to be eligible.

                Predicate values are compared by equality and are not
                evaluated or interpreted by the `Lifetime` itself.
        """
        self.name = name
        self.states = states
        self.initial = initial
        self.terminal = terminal
        self.transitions = transitions
        self.predicates = predicates or {}

        self._compiled: dict[str, list[Edge]] = {}
        self._compile()

    def _compile(self) -> None:
        for source, targets in self.transitions.items():
            for target in targets:
                key = (source, target)
                requires = self.predicates.get(key, {})
                transition = Edge(
                    source=source,
                    target=target,
                    requires=requires,
                    priority=0,
                )
                self._compiled.setdefault(source, []).append(transition)

        for transitions in self._compiled.values():
            transitions.sort(key=lambda t: (-t.priority, t.target))

    def transitions_from(self, state: str) -> list[Edge]:
        return self._compiled.get(state, [])


class PredicateScope(enum.Enum):
    STEP = 0x1
    RUN = 0x2


class PredicateStore(object):
    """
    PredicateStore is a scoped, deterministic fact cache for a single LifetimeRun.
    It exists to own predicate lifetime and lookup rules so the engine never
    has to.

    This class contains no transition logic and performs no evaluation.
    It is a pure data container with deterministic lookup rules.
    """

    def __init__(self) -> None:
        self._step: dict[str, FACT_VALUE] = {}
        """Stores predicates that are ephemeral, cleared on transition."""

        self._run: dict[str, FACT_VALUE] = {}
        """Stores predicates that are persistent for the lifetime of the run."""

    def report(self, name: str, value: FACT_VALUE, scope: PredicateScope) -> None:
        if scope is PredicateScope.STEP:
            self._step[name] = value
        elif scope is PredicateScope.RUN:
            self._run[name] = value
        else:
            raise ValueError(f"Unknown predicate scope: {scope}")

    def resolve(self, name: str) -> Optional[FACT_VALUE]:
        """
        Resolve a predicate value by precedence.

        Order:
        1. Step predicates
        2. Run predicates
        """
        if name in self._step:
            return self._step[name]
        if name in self._run:
            return self._run[name]
        return None

    def clear_step(self) -> None:
        self._step.clear()

    def to_dict(self) -> dict[str, FACT_VALUE]:
        """
        Return a merged view of all predicates for debugging.
        Step predicates override run predicates.
        """
        merged = dict(self._run)
        merged.update(self._step)
        return merged


class LifetimeRun(object):
    """
    Runtime instance of a Lifetime definition.

    LifetimeRun records *what has happened so far* during execution.
    """

    def __init__(self, lifetime: LifetimeDefinition) -> None:
        self.id: uuid.UUID = uuid.uuid4()
        self.lifetime = lifetime
        self.state: str = lifetime.initial
        self.predicates = PredicateStore()
        self.finished: bool = False

    def report_predicate(
        self,
        name: str,
        value: FACT_VALUE,
        *,
        scope: PredicateScope = PredicateScope.STEP,
    ) -> None:
        self.predicates.report(name, value, scope)

    def is_terminal(self) -> bool:
        return self.state in self.lifetime.terminal


class StepResult(enum.Enum):
    ADVANCED = 0x1
    STALLED = 0x2
    FINISHED = 0x4


# -----Broker Namespaces-----
STEP_STARTED = "engine.step.started"
LIFETIME_ADVANCED = "engine.lifetime.state.advanced"
LIFETIME_FINISHED = "engine.lifetime.state.finished"
ENGINE_STALLED = "engine.stalled"


class Engine(object):
    """
    The primary state and lifetime transition manager.

    Singleton class that manages all engine lifetimes in a python runtime.
    """

    _instance: Optional["Engine"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "Engine":
        if cls._instance is None:
            cls._instance = super(Engine, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._runs: dict[uuid.UUID, LifetimeRun] = {}

    def get(self, run_id: uuid.UUID) -> Optional[LifetimeRun]:
        return self._runs.get(run_id)

    def all_runs(self) -> list[LifetimeRun]:
        return list(self._runs.values())

    def start(self, lifetime: LifetimeDefinition) -> LifetimeRun:
        run = LifetimeRun(lifetime)
        self._runs[run.id] = run
        return run

    def step(self, run: LifetimeRun) -> StepResult:
        broker.emit(STEP_STARTED)

        if run.finished:
            broker.emit(LIFETIME_FINISHED, lifetime=run, terminated=False)
            return StepResult.FINISHED

        if run.is_terminal():
            run.finished = True
            broker.emit(LIFETIME_FINISHED, lifetime=run, terminated=True)
            return StepResult.FINISHED

        for transition in run.lifetime.transitions_from(run.state):
            if self._predicates_satisfied(run, transition):
                self._apply_transition(run, transition)
                broker.emit(LIFETIME_ADVANCED, lifetime=run)
                return StepResult.ADVANCED

        broker.emit(ENGINE_STALLED, lifetime=run)
        return StepResult.STALLED

    def step_all(self) -> dict[uuid.UUID, StepResult]:
        results: dict[uuid.UUID, StepResult] = {}

        for run_id, run in list(self._runs.items()):
            result = self.step(run)
            results[run_id] = result

            if result is StepResult.FINISHED:
                self._runs.pop(run_id)

        return results

    @staticmethod
    def _predicates_satisfied(run: LifetimeRun, transition: Edge) -> bool:
        for name, required in transition.requires.items():
            if run.predicates.resolve(name) != required:
                return False
        return True

    @staticmethod
    def _apply_transition(run: LifetimeRun, transition: Edge) -> None:
        run.state = transition.target
        run.predicates.clear_step()

        if run.is_terminal():
            run.finished = True

    @staticmethod
    def why_stalled(run: LifetimeRun) -> list[TransitionBlocker]:
        """
        Explain why no transition could be taken from the current state.

        Returns one entry per possible transition from the current state,
        describing which predicates blocked it.
        """
        blockers: list[TransitionBlocker] = []

        for transition in run.lifetime.transitions_from(run.state):
            missing: dict[str, FACT_VALUE] = {}
            mismatched: dict[str, tuple[FACT_VALUE | None, FACT_VALUE]] = {}

            for name, required in transition.requires.items():
                actual = run.predicates.resolve(name)

                if actual is None:
                    missing[name] = required
                elif actual != required:
                    mismatched[name] = (actual, required)

            if missing or mismatched:
                blockers.append(
                    TransitionBlocker(
                        transition=transition,
                        missing=missing,
                        mismatched=mismatched,
                    )
                )

        return blockers


# Initialize the singleton immediately
_ = Engine()
