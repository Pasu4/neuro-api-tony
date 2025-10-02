import pytest

from neuro_api_tony.model import NeuroAction, TonyModel


@pytest.fixture
def model() -> TonyModel:
    """Fixture to create a TonyModel instance for testing."""
    return TonyModel()


def test_repr(model: TonyModel) -> None:
    """Test that repr works properly."""
    assert repr(model) == "TonyModel()"


def test_add_action(model: TonyModel) -> None:
    """Test adding an action to the model."""
    action = NeuroAction(
        name="test_action",
        description="A test action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    model.add_action(action)
    assert model.actions == [action]


def test_remove_action(model: TonyModel) -> None:
    """Test removing an action from the model."""
    action = NeuroAction(
        name="test_action",
        description="A test action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    model.add_action(action)
    model._remove_action(action)
    assert not model.actions


def test_remove_action_by_name(model: TonyModel) -> None:
    """Test removing an action by name."""
    action1 = NeuroAction(
        name="action1",
        description="First action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    action2 = NeuroAction(
        name="action2",
        description="Second action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    model.add_action(action1)
    model.add_action(action2)
    model.remove_actions(name="action1")
    assert model.actions == [action2]


def test_clear_actions(model: TonyModel) -> None:
    """Test clearing all actions from the model."""
    action = NeuroAction(
        name="test_action",
        description="A test action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    model.add_action(action)
    model.clear_actions()
    assert not model.actions


def test_has_action(model: TonyModel) -> None:
    """Test checking if an action exists in the model."""
    action = NeuroAction(
        name="test_action",
        description="A test action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    model.add_action(action)
    assert model.has_action("test_action")
    assert not model.has_action("non_existent_action")


def test_get_action_by_name(model: TonyModel) -> None:
    """Test getting an action by name."""
    action = NeuroAction(
        name="test_action",
        description="A test action",
        schema=None,
        client_id=0,
        game="test_game",
    )
    model.add_action(action)
    retrieved_action = model.get_action_by_name("test_action")
    assert retrieved_action is action
    assert model.get_action_by_name("non_existent_action") is None
