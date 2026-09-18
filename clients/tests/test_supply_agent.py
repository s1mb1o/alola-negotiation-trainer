import json

import pytest

from clients.agent import NegotiationAgent
from clients.orchestrator import actor_safe_protocol_result
from clients.tests.test_agent import CapturingProvider


@pytest.mark.parametrize("language", ["ru", "en"])
def test_supply_agent_receives_publication_snapshot_and_contract_specific_instructions(language):
    provider = CapturingProvider()
    agent = NegotiationAgent(provider, role="buyer", language=language)
    pending = {"proposal_id": "proposal_test", "proposal_revision": 3,
               "terms": {"base_price": {"currency": "EUR", "minor_units": 10950000}},
               "snapshot_digest": "sha256:test", "unresolved_required_terms": []}
    protocol = actor_safe_protocol_result({"result": "confirmation_required", "confirmation_kind": "publish_offer",
        "negotiation_contract_version": "supply-package-v1", "pending_offer_publication": pending,
        "observation": {"role_brief": "another participant's brief"}, "private_state": {"budget": 1}})
    agent.generate_turn(observation={"negotiation_contract_version": "supply-package-v1", "preliminary_proposals": []},
                        history=[], protocol_result=protocol)
    assert "pending_offer_publication" in protocol
    assert "observation" not in protocol and "private_state" not in protocol
    assert "supply-agent-v1" in provider.instructions[0]
    assert "Preliminary proposals are NEVER formal offers" in provider.instructions[0]
    assert "Подтверждаю окончательное предложение" in provider.instructions[0]
    assert "I confirm the final offer" in provider.instructions[0]
    assert "if/then conditional packages" not in provider.instructions[0]
    context = json.loads(provider.prompts[0].split("\n\n", 1)[1])
    assert context["protocol_result"]["pending_offer_publication"] == pending
