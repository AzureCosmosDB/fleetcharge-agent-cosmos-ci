import json

import pytest

from app.vehicle_questions import validate_vehicle_answer


def test_generated_count_and_ids_must_match_actual_records():
    answer = validate_vehicle_answer(
        json.dumps(
            {
                "answer": "There are 3 vehicles in the depot.",
                "vehicleCount": 3,
                "vehicleIds": ["van-c", "van-a", "van-b"],
            }
        ),
        ["van-a", "van-b", "van-c"],
    )
    assert answer.vehicle_count == 3


@pytest.mark.parametrize(
    "mutation",
    [
        {"vehicleCount": 2},
        {"vehicleIds": ["van-a", "invented"]},
        {"vehicleIds": ["van-a", "van-a"]},
        {"answer": "There are 9 vehicles in the depot."},
    ],
)
def test_invented_count_or_ids_fail_instead_of_being_repaired(mutation):
    value = {
        "answer": "There are 2 vehicles in the depot.",
        "vehicleCount": 2,
        "vehicleIds": ["van-a", "van-b"],
    }
    if mutation == {"vehicleCount": 2}:
        mutation = {"vehicleCount": 3}
    with pytest.raises(ValueError):
        validate_vehicle_answer(json.dumps({**value, **mutation}), ["van-a", "van-b"])
