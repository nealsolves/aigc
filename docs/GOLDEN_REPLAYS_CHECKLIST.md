# Golden Replay Checklist

This checklist is a machine-readable, human-verifiable summary of
requirements for golden replay compliance.

Use this as a PR checklist or CI rule reference.

---

## 🔍 1. Directory Structure

```text
tests/
├── golden_replays/
│   ├── golden_policy_.yaml
│   ├── golden_schema_.json
│   ├── golden_invocation_success_.json
│   ├── golden_invocation_failure_.json
│   └── golden_expected_audit_*.json
```

- [ ] All required golden artifacts exist  
- [ ] Naming includes version tags (v1, v2, etc.)

---

## 🤖 2. Golden Policy Files

- [ ] Policy names include version
- [ ] Roles are defined
- [ ] Preconditions and postconditions are present
- [ ] Enforcement mode is explicit

---

## 📐 3. Schema Files

- [ ] JSON schema conforms to draft-07 or newer
- [ ] Required fields are defined

---

## 🧪 4. Success Golden Invocations

- [ ] Contains valid input
- [ ] Output satisfies schema
- [ ] Context flags satisfy policy preconditions

---

## ❌ 5. Failure Golden Invocations

- [ ] Missing required fields to induce failure
- [ ] Policy constraints deliberately violated

---

## 🧾 6. Expected Audit Contracts

- [ ] Contains `model_provider`
- [ ] Contains `model_identifier`
- [ ] Contains `role`
- [ ] Contains `policy_version`
- [ ] Contains `policy_file`
- [ ] Contains `policy_schema_version`
- [ ] Contains `enforcement_result`
- [ ] Avoids transient fields (e.g., timestamp)

---

## 📈 7. Test Files

- [ ] `test_golden_replay_success.py` exists
- [ ] `test_golden_replay_failure.py` exists
- [ ] Optional: `test_golden_replay_edgecases.py`
- [ ] `test_audit_artifact_contract.py`

---

## 🔁 8. Version Control

- [ ] Golden replay changes are intentional and documented  
- [ ] Golden fixture version increments on change

---

## 📊 9. CI Integration

- [ ] CI runs golden replay tests
- [ ] CI blocks merge on failure
- [ ] Test failure output includes artifact differences

---

## 👥 10. Team Awareness

- [ ] Team knows how to update golden replays
- [ ] Team knows when new golden replays are required

---

## ✅ Sign-off

By checking all the above boxes, you confirm that:

> Golden replays fully cover core governance enforcement behaviors
> and are ready for automated validation in CI.
