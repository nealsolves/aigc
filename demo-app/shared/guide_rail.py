"""Lab guide rail — contextual help system for each lab.

Provides four display modes:
  - linear:     Numbered steps with completion tracking (Labs 1, 4)
  - workflows:  Selectable workflow cards with sub-steps (Labs 2, 5)
  - iterative:  Repeating cycle with milestone progress (Lab 3)
  - cookbook:    Named recipes with "Load" buttons (Lab 6)

Rendered in the right 25% column via st.columns([3, 1]).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import streamlit as st


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class GuideStep:
    """A single step in a lab guide."""

    title: str
    instruction: str
    what_to_expect: str
    completion_key: str | None = None  # session_state key marking completion
    show_me: Callable | None = None    # pre-fill callback


@dataclass
class GuideWorkflow:
    """A named workflow with ordered steps (for branching labs)."""

    name: str
    description: str
    steps: list[GuideStep] = field(default_factory=list)


@dataclass
class GuideRecipe:
    """A code recipe for cookbook-mode labs."""

    name: str
    description: str
    code: str
    what_it_demonstrates: str


@dataclass
class LabGuide:
    """Complete guide configuration for one lab."""

    lab_id: str
    title: str
    overview: str
    mode: str  # "linear" | "workflows" | "iterative" | "cookbook"

    # Mode-specific fields
    steps: list[GuideStep] | None = None             # linear
    workflows: list[GuideWorkflow] | None = None      # workflows
    recipes: list[GuideRecipe] | None = None           # cookbook
    iteration_target: int | None = None                # iterative
    iterative_steps: list[GuideStep] | None = None     # iterative cycle steps

    glossary: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------
def render_lab_guide(guide: LabGuide) -> None:
    """Render the guide rail for a lab.

    Call inside the right column of st.columns([3, 1]).
    """
    # Toggle visibility
    vis_key = f"guide_visible_{guide.lab_id}"
    if vis_key not in st.session_state:
        st.session_state[vis_key] = True

    if st.button(
        "Hide Guide" if st.session_state[vis_key] else "Show Guide",
        key=f"guide_toggle_{guide.lab_id}",
        use_container_width=True,
    ):
        st.session_state[vis_key] = not st.session_state[vis_key]
        st.rerun()

    if not st.session_state[vis_key]:
        return

    st.subheader(guide.title)
    st.caption(guide.overview)
    st.divider()

    if guide.mode == "linear":
        _render_linear(guide)
    elif guide.mode == "workflows":
        _render_workflows(guide)
    elif guide.mode == "iterative":
        _render_iterative(guide)
    elif guide.mode == "cookbook":
        _render_cookbook(guide)

    # Glossary
    if guide.glossary:
        with st.expander("Glossary"):
            for term, definition in guide.glossary.items():
                st.markdown(f"**{term}:** {definition}")


# ---------------------------------------------------------------------------
# LINEAR mode — Labs 1, 4
# ---------------------------------------------------------------------------
def _render_linear(guide: LabGuide) -> None:
    """Vertical numbered steps with completion dots."""
    if not guide.steps:
        return

    active_idx = _find_active_step(guide.steps)

    for i, step in enumerate(guide.steps):
        completed = _is_step_complete(step)
        is_active = i == active_idx

        # Status indicator
        if completed:
            icon = "\U0001f7e2"  # green circle
        elif is_active:
            icon = "\U0001f535"  # blue circle
        else:
            icon = "\u26aa"      # white circle

        st.markdown(f"### {icon} Step {i + 1}: {step.title}")
        st.markdown(f"_{step.instruction}_")

        if is_active or completed:
            st.caption(f"What to expect: {step.what_to_expect}")

        if is_active and step.show_me:
            if st.button(f"Show Me", key=f"showme_{guide.lab_id}_{i}"):
                step.show_me()
                st.rerun()

        if i < len(guide.steps) - 1:
            st.markdown("---")


# ---------------------------------------------------------------------------
# WORKFLOWS mode — Labs 2, 5
# ---------------------------------------------------------------------------
def _render_workflows(guide: LabGuide) -> None:
    """Selectable workflow cards with sub-steps."""
    if not guide.workflows:
        return

    sel_key = f"guide_workflow_{guide.lab_id}"
    names = [w.name for w in guide.workflows]

    selected = st.radio(
        "Choose a workflow",
        names,
        key=sel_key,
        label_visibility="collapsed",
    )

    for wf in guide.workflows:
        if wf.name == selected:
            st.markdown(f"**{wf.name}**")
            st.caption(wf.description)
            st.divider()

            active_idx = _find_active_step(wf.steps)
            for i, step in enumerate(wf.steps):
                completed = _is_step_complete(step)
                is_active = i == active_idx
                icon = "\U0001f7e2" if completed else ("\U0001f535" if is_active else "\u26aa")

                st.markdown(f"{icon} **{step.title}**")
                st.caption(step.instruction)

                if is_active and step.show_me:
                    if st.button("Show Me", key=f"showme_{guide.lab_id}_{wf.name}_{i}"):
                        step.show_me()
                        st.rerun()
            break


# ---------------------------------------------------------------------------
# ITERATIVE mode — Lab 3
# ---------------------------------------------------------------------------
def _render_iterative(guide: LabGuide) -> None:
    """Repeating cycle with milestone progress bar."""
    target = guide.iteration_target or 5
    chain_len = st.session_state.get("chain", None)
    current = chain_len.length if chain_len else 0

    # Progress bar
    progress = min(current / target, 1.0)
    st.progress(progress)
    st.caption(f"{current} / {target} artifacts linked")

    if current >= target:
        st.success("Milestone reached!")

    # Show cycle steps
    if guide.iterative_steps:
        st.markdown("**Repeating cycle:**")
        for i, step in enumerate(guide.iterative_steps):
            st.markdown(f"{i + 1}. {step.title}")
            st.caption(step.instruction)

    # Chain history
    history = st.session_state.get("audit_history", [])
    chain_artifacts = [a for a in history if a.get("chain_id")]
    if chain_artifacts:
        with st.expander(f"Chain history ({len(chain_artifacts)} links)"):
            for a in chain_artifacts:
                idx = a.get("chain_index", "?")
                cksum = a.get("checksum", "—")[:12]
                st.caption(f"#{idx} — {cksum}...")


# ---------------------------------------------------------------------------
# COOKBOOK mode — Lab 6
# ---------------------------------------------------------------------------
def _render_cookbook(guide: LabGuide) -> None:
    """Named recipes with Load buttons."""
    if not guide.recipes:
        return

    for recipe in guide.recipes:
        with st.container(border=True):
            st.markdown(f"**{recipe.name}**")
            st.caption(recipe.description)
            st.caption(f"Demonstrates: {recipe.what_it_demonstrates}")

            if st.button("Load", key=f"recipe_{guide.lab_id}_{recipe.name}"):
                st.session_state[f"{guide.lab_id}_selected_recipe"] = recipe.name
                st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_step_complete(step: GuideStep) -> bool:
    """Check if a step's completion key is set in session state."""
    if step.completion_key is None:
        return False
    return bool(st.session_state.get(step.completion_key))


def _find_active_step(steps: list[GuideStep]) -> int:
    """Return the index of the first incomplete step (or last step)."""
    for i, step in enumerate(steps):
        if not _is_step_complete(step):
            return i
    return len(steps) - 1
