# Golden Trace Checklist

This checklist is a machine-readable, human-verifiable summary of
requirements for golden trace compliance.

Use this as a PR checklist or CI rule reference.

---

## 🔍 1. Directory Structure

```text
tests/
├── golden_traces/
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
- [ ] Avoids transient fields (e.g., timestamp)

---

## 📈 7. Test Files

- [ ] `test_golden_trace_success.py` exists
- [ ] `test_golden_trace_failure.py` exists
- [ ] Optional: `test_golden_trace_edgecases.py`
- [ ] `test_audit_artifact_contract.py`

---

## 🔁 8. Version Control

- [ ] Golden trace changes are intentional and documented  
- [ ] Golden fixture version increments on change

---

## 📊 9. CI Integration

- [ ] CI runs golden trace tests
- [ ] CI blocks merge on failure
- [ ] Test failure output includes artifact differences

---

## 👥 10. Team Awareness

- [ ] Team knows how to update golden traces
- [ ] Team knows when new golden traces are required

---

## ✅ Sign-off

By checking all the above boxes, you confirm that:

> Golden traces fully cover core governance enforcement behaviors
> and are ready for automated validation in CI.
