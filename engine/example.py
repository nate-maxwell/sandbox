"""
Simple approval workflow using the state engine.

A document goes through: draft -> review -> approved/rejected
"""

import time
import shutil
import sys
from typing import Any

import broker

import engine


def print_header(s: str) -> None:
    w, _ = shutil.get_terminal_size()
    print("\n" + "=" * w)
    print(s.center(w))
    print("=" * w + "\n")


class Document(object):
    """A document that needs approval."""

    def __init__(self, title: str, content: str) -> None:
        self.title = title
        self.content = content
        self.reviewer_notes = ""

    def check_quality(self) -> bool:
        # Simple check: must have title and content
        has_content = len(self.content.strip()) > 10
        has_title = len(self.title.strip()) > 0

        print(f"  Quality check: title={has_title}, content={has_content}")
        return has_content and has_title

    def review(self) -> bool:
        # Documents with "urgent" in title get approved, others rejected
        approved = "urgent" in self.title.lower()

        if approved:
            self.reviewer_notes = "Approved - urgent request"
        else:
            self.reviewer_notes = "Rejected - not urgent"

        print(f"  Review result: {self.reviewer_notes}")
        return approved


class ApprovalWorkflow(object):
    """Manages document approval through state transitions."""

    def __init__(self) -> None:
        self.engine_instance = engine.Engine()
        self.documents = {}

        # Subscribe to engine events
        broker.register_subscriber(engine.LIFETIME_ADVANCED, self.on_state_changed)

    def create_lifetime(self) -> engine.LifetimeDefinition:
        """Define the approval state machine."""
        return engine.LifetimeDefinition(
            name="approval",
            states={"draft", "reviewing", "approved", "rejected"},
            initial="draft",
            terminal={"approved", "rejected"},
            transitions={
                "draft": {"reviewing"},
                "reviewing": {"approved", "rejected"},
            },
            predicates={
                ("reviewing", "approved"): {"quality_ok": True, "review_ok": True},
                ("reviewing", "rejected"): {"review_ok": False},
            },
        )

    def process_document(self, doc: Document) -> None:
        """Process a document through the approval workflow."""
        print_header(f"Processing: {doc.title}")

        lifetime = self.create_lifetime()
        run = self.engine_instance.start(lifetime)
        self.documents[run.id] = doc

        print(f"State: {run.state}")

        # Step through workflow
        while True:
            # Perform actions based on current state
            if run.state == "draft":  # Check quality before moving to review
                quality_ok = doc.check_quality()
                run.report_predicate(
                    "quality_ok", quality_ok, scope=engine.PredicateScope.RUN
                )

            elif run.state == "reviewing":
                review_ok = doc.review()
                run.report_predicate(
                    "review_ok", review_ok, scope=engine.PredicateScope.RUN
                )

            # Advance the engine
            result = self.engine_instance.step(run)

            if result == engine.StepResult.FINISHED:
                print(f"Final state: {run.state}")
                break
            elif result == engine.StepResult.STALLED:
                print(f"Stalled in state: {run.state}")
                break

            time.sleep(0.2)

    def on_state_changed(self, **kwargs: Any) -> None:
        """Called when state changes."""
        lifetime_run = kwargs.get("lifetime")
        if lifetime_run:
            print(f"→ Transitioned to: {lifetime_run.state}")


def main() -> int:
    workflow = ApprovalWorkflow()

    docs = [
        Document(
            "Urgent: Server Migration",
            "We need to migrate servers ASAP. This is critical.",
        ),
        Document("Meeting Notes", "Today we discussed various topics."),
        Document("", "Some content but no title"),
        Document(
            "Urgent: Handbook for the Recently Deceased",
            "Lorem ipsum dolor sit amet...",
        ),
    ]

    for doc in docs:
        workflow.process_document(doc)
        time.sleep(0.5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
