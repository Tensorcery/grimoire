# Severity

Judge by consequence, not by how clever the defect is or how hard it was to
find.

| Level | Meaning | In code | In a document or deck |
|---|---|---|---|
| `critical` | The target is wrong in what matters most | Money or data lost or exposed; access control bypassed by anyone who can reach the system | The central conclusion or headline number is false |
| `high` | It fails or misleads under realistic conditions | A rule the target states is broken in normal use; data of one user visible to another who is logged in | A figure a reader will act on is wrong; a claim says the opposite of its source |
| `medium` | A real defect that needs unusual conditions or has limited effect | Wrong result on an edge input; small systematic error | A table that does not add up; two places that disagree on a secondary figure |
| `low` | A minor inaccuracy or a missing safeguard | A wrong counter; a missing limit with no shown abuse | Loose wording, a rounding slip that changes nothing |
| `info` | An observation worth knowing | A smell, a structural weakness, an untested area | Style, layout, an unclear label |

## Rules

- Between two levels, take the lower one and state what would raise it.
- `critical` and `high` need evidence that was run or quoted, never a
  suspicion.
- What the target's own documents list as a limitation is `info` at most.
- Severity is about this target as its documents describe it. A missing
  feature nobody promised is not a defect.
- Structure, architecture and maturity observations (category `design`)
  follow the same scale: `high` only when the structure itself makes a stated
  rule impossible to keep, otherwise `medium` and below.
- Likelihood matters. Something any user can trigger by accident is a level
  above the same thing behind an administrator's password.
