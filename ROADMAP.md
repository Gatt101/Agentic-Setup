# OrthoAssist — Product Roadmap

> Multi-Agent Orthopedic Diagnosis System
> Last updated: April 2026

---

## Phase 1 — Foundation Fixes & Quick Wins (Weeks 1–3)

**Goal:** Fix existing bugs and ship the highest-ROI features that immediately improve doctor trust and daily workflow.

### Bug Fixes
- [ ] Fix `feedback.py` import (`chatai_store` → `chat_store`)
- [ ] Fix `vision_agent.py` `self.clinical_context` AttributeError (lines 295, 327)
- [ ] Fix vision tool parameter naming mismatch (`image_base64` vs `image_data`)
- [ ] Add rate limiting middleware
- [ ] Tighten CORS config for production

### Quick Wins
- [ ] **Evidence citations** — Every diagnosis cites clinical guidelines (AAOS, OTA, AO Foundation)
- [ ] **CPT/ICD-10 code lookup** — Auto-suggest billing codes from diagnosis
- [ ] **Red flags checklist** — Systematic screening for open fractures, neurovascular compromise, compartment syndrome, pathological fractures
- [ ] **Image quality assurance** — Pre-analysis check for rotation, exposure, positioning; reject and suggest re-take
- [ ] **Follow-up scheduler** — Auto-suggest follow-up intervals based on triage (red=24–48h, amber=3–5 days, green=2 weeks)
- [ ] **Streaming responses** — Migrate chat from JSON polling to SSE/streaming (Vercel AI SDK already installed)

### Infrastructure
- [ ] Add unit and integration tests (currently 0 tests)
- [ ] Set up CI/CD pipeline
- [ ] Add proper `middleware.ts` for Next.js

---

## Phase 2 — DICOM + Multi-Modal Input (Weeks 3–5)

**Goal:** Accept DICOM uploads, auto-detect modality (X-ray/CT/MRI), and integrate pre-trained CT/MRI analysis using existing open-source models — zero training required.

### Strategy: API-First, Train Later

Instead of training models from scratch, use pre-trained open-source models:

| Need | Model | Source | License |
|------|-------|--------|---------|
| CT: Full bone segmentation (117 classes — femur, tibia, vertebrae, ribs, pelvis, etc.) | **TotalSegmentator** | `pip install TotalSegmentator` | Apache-2.0 |
| CT: Appendicular bones (foot, ankle, hand, knee, wrist bones) | TotalSegmentator `appendicular_bones` task | Same package | Free non-commercial |
| CT: Spine vertebrae (C1–S1, 25 classes) | TotalSegmentator `vertebrae_body` task | Same package | Free non-commercial |
| CT: Spine vertebrae (dedicated, higher accuracy) | **VerSe nnUNet** | `huggingface-cli download lukatman/verse-vertebrae-segmentation-nnunet` | Apache-2.0 |
| MRI: Vertebrae (C1–S1) | TotalSegmentator `vertebrae_mr` task | Same package | Apache-2.0 |
| MRI: Knee bone + cartilage | **SKI10 Random Forest** | `pip install kneeseg` + HF model `wq2012/knee_3d_mri_segmentation_SKI10` | MIT |

**All models support CPU inference.** GPU can be added later for speed.

### 2.1 DICOM Upload + Modality Detection (Week 3)

**New files:**
- `backend/tools/modality/__init__.py` — Exports `MODALITY_TOOLS`
- `backend/tools/modality/detect_modality.py` — Auto-detect imaging modality from DICOM metadata or image heuristics
- `backend/tools/modality/dicom_parser.py` — Parse DICOM files, extract metadata, convert to NIfTI for model consumption

**New tools:**
| Tool | Purpose |
|------|---------|
| `modality_detect_imaging_modality` | Detect X-ray/CT/MRI from DICOM `Modality` tag (0008,0060) or fallback to image heuristics |
| `modality_parse_dicom` | Parse DICOM file(s), return metadata dict + NIfTI volume path |
| `modality_extract_mid_slice` | Extract middle slice from 3D volume as PNG base64 for preview |

**New dependencies:**
```
pydicom>=3.0.0
SimpleITK>=2.3.0
nibabel>=5.2.0
TotalSegmentator>=2.2.0
kneeseg  # knee MRI segmentation
```

**API changes:**
- `backend/api/schemas/requests.py` — Add `dicom_files: list[UploadFile]` and `modality: str | None` to `AnalyzeRequest`
- `backend/api/endpoints/analyze.py` — Handle DICOM multipart upload alongside existing base64 path
- DICOM files stored in `storage/raw/dicom/`, converted NIfTI in `storage/raw/nifti/`

**State changes (`backend/graph/state.py`):**
```python
modality: str | None               # "xray" | "ct" | "mri"
body_region: str | None            # "hand" | "leg" | "knee" | "spine" | "foot" | "pelvis" | "shoulder"
volume_path: str | None            # Path to NIfTI volume on disk
dicom_metadata: dict | None        # Extracted DICOM tags
ct_findings: list[dict] | None     # CT-specific findings (from TotalSegmentator/VerSe)
mri_findings: list[dict] | None    # MRI-specific findings
```

### 2.2 CT Analysis Tools (Week 4)

**New files:**
- `backend/tools/ct/__init__.py` — Exports `CT_TOOLS`
- `backend/tools/ct/ct_runtime.py` — TotalSegmentator + VerSe nnUNet runtime wrapper
- `backend/tools/ct/bone_segmentation.py` — Full body bone segmentation
- `backend/tools/ct/spine_segmentation.py` — Dedicated vertebrae segmentation
- `backend/tools/ct/appendicular_segmentation.py` — Foot/ankle/hand/knee bone segmentation

**New tools:**
| Tool | Model | Task |
|------|-------|------|
| `ct_analyze_full_body` | TotalSegmentator `total` | Full 117-class CT segmentation (femur, tibia, pelvis, vertebrae, ribs, etc.) |
| `ct_analyze_spine` | VerSe nnUNet | Dedicated C1–S1 vertebrae segmentation (higher accuracy than TotalSegmentator) |
| `ct_analyze_appendicular` | TotalSegmentator `appendicular_bones` | Foot, ankle, hand, wrist, knee, elbow bones |

**Tool output format (standardized across all CT tools):**
```json
{
  "findings": [
    {"label": "femur_left", "score": 0.94, "volume_mm3": 245000, "location": {"side": "left", "region": "thigh"}},
    {"label": "vertebra_L1", "score": 0.89, "volume_mm3": 32000, "location": {"vertebra": "L1", "level": "lumbar"}}
  ],
  "summary": {"total_structures": 47, "abnormal_count": 0, "regions_analyzed": ["pelvis", "spine", "legs"]},
  "segmentation_mask_path": "/storage/segmentations/<uuid>.nii.gz",
  "annotated_slices_base64": ["data:image/png;base64,..."],
  "volume_info": {"shape": [512, 512, 256], "spacing_mm": [0.5, 0.5, 1.0]}
}
```

**Runtime architecture (`ct_runtime.py`):**
```python
from totalsegmentator.python_api import totalsegmentator

async def run_totalsegmentator(volume_path: str, task: str, device: str = "cpu", fast: bool = True) -> dict:
    """Run TotalSegmentator in a thread (non-blocking)."""
    output_dir = f"/tmp/ct_seg_{uuid4()}"
    result = await asyncio.to_thread(
        totalsegmentator,
        input_path=volume_path,
        output_path=output_dir,
        task=task,
        device=device,
        fast=fast,
    )
    # Parse segmentation NIfTI masks → extract labels, volumes, locations
    # Generate annotated slice PNGs → return as base64
    return findings_dict
```

### 2.3 MRI Analysis Tools (Week 4–5)

**New files:**
- `backend/tools/mri/__init__.py` — Exports `MRI_TOOLS`
- `backend/tools/mri/mri_runtime.py` — kneeseg + TotalSegmentator MRI runtime wrapper
- `backend/tools/mri/knee_segmentation.py` — Knee bone + cartilage segmentation
- `backend/tools/mri/spine_segmentation.py` — MRI vertebrae segmentation

**New tools:**
| Tool | Model | Task |
|------|-------|------|
| `mri_analyze_knee` | SKI10 (kneeseg) | Knee bone + cartilage segmentation (femur, tibia, patella, femoral/tibial cartilage) |
| `mri_analyze_spine` | TotalSegmentator `vertebrae_mr` | MRI vertebrae segmentation (C1–S1) |

**Tool output format:**
```json
{
  "findings": [
    {"label": "femoral_cartilage", "score": 0.72, "volume_mm3": 8500, "location": {"compartment": "medial"}},
    {"label": "tibia", "score": 0.95, "volume_mm3": 180000, "location": {"side": "left"}},
    {"label": "tibial_cartilage", "score": 0.68, "volume_mm3": 6200, "location": {"compartment": "lateral"}}
  ],
  "summary": {"total_structures": 6, "cartilage_integrity": "reduced_medial"},
  "segmentation_mask_path": "/storage/segmentations/<uuid>.nii.gz",
  "annotated_slices_base64": ["data:image/png;base64,..."]
}
```

### 2.4 Supervisor & Graph Updates (Week 4)

**`backend/graph/nodes/supervisor.py` — Modality-aware routing:**
```
Upload → detect_modality
  ├── "xray" → existing YOLO pipeline (vision_detect_body_part → detect_hand/leg_fracture)
  ├── "ct"   → ct_analyze_full_body OR ct_analyze_spine OR ct_analyze_appendicular
  └── "mri"  → mri_analyze_knee OR mri_analyze_spine

All paths → clinical_generate_diagnosis → clinical_assess_triage → report → response
```

**`backend/graph/nodes/tool_executor.py`:**
- Inject `volume_path` into all `ct_*` and `mri_*` tool calls (same pattern as `image_base64` injection)
- Map `ct_*` results → `state["ct_findings"]`, `mri_*` results → `state["mri_findings"]`
- Unify for clinical tools: `findings = detections OR ct_findings OR mri_findings`

**`backend/tools/__init__.py`:**
```python
from tools.modality import MODALITY_TOOLS
from tools.ct import CT_TOOLS
from tools.mri import MRI_TOOLS

ALL_TOOLS = [*MODALITY_TOOLS, *VISION_TOOLS, *CT_TOOLS, *MRI_TOOLS, *CLINICAL_TOOLS, ...]
```

**`backend/tools/vision/body_part_detector.py` — Expand body parts:**
- Add "knee", "spine", "foot", "ankle", "pelvis", "shoulder", "wrist" to body part classifier
- Use DICOM `BodyPartExamined` tag when available, aspect-ratio heuristic as fallback

### 2.5 Report & Clinical Integration (Week 5)

- Update `backend/tools/clinical/diagnosis.py` — Accept `ct_findings` / `mri_findings` alongside `detections`
- Update `backend/tools/clinical/diagnosis.py` — Modality-aware diagnosis templates:
  - X-ray: "Fracture detected in {body_part}..."
  - CT: "CT segmentation reveals {n} structures analyzed. Findings: {list}..."
  - MRI: "MRI evaluation of {body_region} demonstrates {findings}. Cartilage integrity: {status}..."
- Update report PDF generators — Add modality badge, annotated slices, DICOM metadata section
- Update `backend/tools/vision/annotator.py` — Handle volumetric segmentation overlay on key slices

### 2.6 Frontend Updates (Week 5)

- Upload component — Add DICOM drag-and-drop (`.dcm` files or `.zip` of DICOM series)
- Modality badge — Show X-RAY / CT / MRI after upload
- DICOM metadata preview — Study date, body part, scanner, slice count
- Results display — Scrollable annotated slice gallery for CT/MRI (not just one image)
- Chat integration — Handle DICOM file attachments in `useChat` hook

### 2.7 New Dependencies (`requirements.txt`)
```
pydicom>=3.0.0
SimpleITK>=2.3.0
nibabel>=5.2.0
TotalSegmentator>=2.2.0
nnunetv2>=2.4.0           # For VerSe model inference
```

### 2.8 Validation Milestones

| Milestone | Criteria | Target |
|-----------|----------|--------|
| DICOM upload works | Upload `.dcm`, correct modality + body part detected | Week 3 |
| CT spine segmentation | Run VerSe on test CT, get vertebrae labels | Week 4 |
| CT full body | Run TotalSegmentator on test CT, get bone labels | Week 4 |
| MRI knee segmentation | Run SKI10 on test MRI, get bone + cartilage | Week 5 |
| End-to-end CT | Upload CT → analysis → diagnosis → triage → report | Week 5 |
| End-to-end MRI | Upload MRI → analysis → diagnosis → triage → report | Week 5 |

### 2.9 Limitations & Future Training

**Current gap (no pre-trained model exists):** Knee MRI pathology detection (ACL tear, meniscus tear). The SKI10 model does bone/cartilage segmentation but cannot detect tears or soft tissue pathology.

**Training plan (future, separate phase):**
1. Collect labeled knee MRI dataset with pathology annotations (MRNet + hospital data)
2. Fine-tune MONAI 3D UNet for ACL/meniscus/cartilage tear classification
3. Fine-tune MONAI for spine MRI disc herniation detection
4. Replace SKI10 segmentation with pathology detection model
5. Fine-tune TotalSegmentator on hospital-specific CT data for better local accuracy

---

## Phase 3 — New Agents (Weeks 6–10)

**Goal:** Add specialized agents that expand the system beyond imaging analysis into full clinical workflow support.

### 3.1 Second Opinion Agent
- [ ] Cross-validate diagnosis against clinical guidelines
- [ ] Confidence scoring on borderline detections
- [ ] Differential diagnosis suggestions
- [ ] Tools: `validate_diagnosis`, `score_confidence`, `suggest_differentials`

### 3.2 Drug Interaction Agent
- [ ] Medication cross-reference with patient history
- [ ] Contraindication flags (NSAIDs + anticoagulants, bisphosphonates + healing, etc.)
- [ ] Antibiotic prophylaxis recommendations for surgical cases
- [ ] Tools: `check_drug_interactions`, `suggest_antibiotic_prophylaxis`, `get_medication_safety`

### 3.3 Surgical Planning Agent
- [ ] Pre-operative planning from imaging findings (X-ray + CT + MRI)
- [ ] Implant sizing recommendations (plates, screws, nails, K-wires)
- [ ] Surgical approach suggestions per fracture type/classification
- [ ] Post-operative follow-up imaging comparison (healing progress)
- [ ] Tools: `plan_surgery`, `suggest_implants`, `compare_followup`, `assess_healing`

### 3.4 Insurance & Billing Agent
- [ ] CPT code suggestion from diagnosis + procedure
- [ ] ICD-10 code lookup from detected conditions
- [ ] Pre-authorization checklist for common orthopedic surgeries
- [ ] Tools: `suggest_cpt_codes`, `lookup_icd10`, `generate_preauth_checklist`

---

## Phase 4 — Advanced Imaging Features (Weeks 11–15)

**Goal:** Deeper imaging analysis beyond detection — measurements, comparison, expanded body regions.

### 4.1 Automated Measurements
- [ ] **Cobb angle** — Scoliosis measurement from spine X-ray/CT
- [ ] **Baumann angle** — Distal humerus fracture assessment
- [ ] **Radial inclination / ulnar variance** — Wrist fracture assessment
- [ ] **Bone length discrepancy** — Leg length measurement from full-leg X-ray
- [ ] Use segmentation masks from CT/MRI tools as input for measurements

### 4.2 Comparison & Timeline
- [ ] **Side-by-side comparison** — Current vs. prior imaging with AI-highlighted changes
- [ ] **Multi-study timeline** — Visual timeline of a patient's imaging over time
- [ ] **Healing progress tracking** — Compare pre/post-op CT, measure callus formation

### 4.3 Expanded YOLO Models (X-ray)
- [ ] Add shoulder detection model
- [ ] Add spine detection model
- [ ] Add pelvis detection model
- [ ] Add wrist/foot detection models
- [ ] Active learning loop: doctor corrections → model retraining

### 4.4 RAG Pipeline (Actual Implementation)
- [ ] Ingest orthopedic textbooks, guidelines, papers into vector store
- [ ] Replace LLM-only knowledge tools with real semantic search
- [ ] Cite specific passages from source documents

---

## Phase 5 — Clinical Workflow & Collaboration (Weeks 16–20)

**Goal:** Make OrthoAssist the central hub for orthopedic clinical workflow.

### 5.1 Voice Dictation
- [ ] Speech-to-text for doctor narrations during image review
- [ ] Auto-structure dictated findings into report format
- [ ] Support for medical terminology (custom STT model fine-tuning)

### 5.2 Doctor Collaboration
- [ ] **Referral note generation** — Auto-generated structured referral summaries
- [ ] **Annotation sharing** — Doctors annotate on AI bounding boxes/segmentations, save for discussion
- [ ] **Multi-specialty routing** — Flag non-orthopedic findings and suggest referrals
- [ ] **Case discussion threads** — Multiple doctors can comment on a single case

### 5.3 Template System
- [ ] Custom report templates per doctor/hospital
- [ ] Pre-filled sections for common fracture types
- [ ] Hospital-specific headers, logos, disclaimers

### 5.4 Batch Processing
- [ ] Upload multiple images/DICOM series for a single patient
- [ ] Consolidated analysis across all images
- [ ] One report for a multi-image study

### 5.5 PACS Integration
- [ ] HL7/DICOM connector for hospital PACS systems
- [ ] Pull images directly from PACS (no manual upload)
- [ ] Push annotated reports back to PACS/EHR

---

## Phase 6 — Patient-Facing Features & Safety (Weeks 21–26)

**Goal:** Complete the patient experience and build patient safety mechanisms.

### 6.1 Patient Communication
- [ ] **Patient-friendly explanations** — Convert complex findings to simple language with visual aids
- [ ] **Discharge summary generator** — One-click discharge paperwork with instructions
- [ ] **Consent form generation** — Procedure-specific informed consent templates
- [ ] Patient chat page (`/dashboard/patient/chat`)
- [ ] Patient nearby hospitals page (`/dashboard/patient/nearby`)

### 6.2 Risk Scoring
- [ ] Complication risk prediction (non-union, infection, DVT, malunion)
- [ ] Patient-specific risk factors analysis (age, comorbidities, smoking, diabetes)
- [ ] Risk-adjusted follow-up recommendations

### 6.3 Rehabilitation Agent
- [ ] Physiotherapy protocol generation per diagnosis
- [ ] Weight-bearing progression timeline (NWB → TTWB → PWB → FWB)
- [ ] ROM exercise recommendations per joint/injury
- [ ] Splint/cast/brace duration recommendations
- [ ] Tools: `generate_rehab_protocol`, `get_weight_bearing_progression`, `suggest_rom_exercises`

---

## Phase 7 — Education, Intelligence & Scale (Weeks 27–34)

**Goal:** Make the system smarter over time and useful for teaching.

### 7.1 "Teach Me" Mode
- [ ] Toggle that makes the agent explain reasoning step-by-step
- [ ] Useful for residents, medical students, junior doctors
- [ ] Interactive quizzes based on uploaded cases

### 7.2 Case Library
- [ ] Anonymized interesting cases for teaching rounds
- [ ] Searchable by diagnosis, fracture type, complexity
- [ ] Case of the week feature

### 7.3 Guideline Lookup
- [ ] Quick access to AO/OTA classification systems
- [ ] Salter-Harris classification reference
- [ ] Gustilo-Anderson open fracture classification
- [ ] Neer/Hill-Sachs/Bankart for shoulder
- [ ] Embedded visual decision trees

### 7.4 Follow-Up Agent
- [ ] Automated follow-up scheduling based on injury severity
- [ ] Healing milestone tracking (union stages, callus formation)
- [ ] Reminder notifications for doctors and patients
- [ ] Tools: `schedule_followup`, `track_healing_milestone`, `generate_followup_summary`

### 7.5 Learning System Enhancements
- [ ] Real LLM-based consensus building (replace hardcoded thresholds)
- [ ] Multi-agent coordination improvements (true parallel execution)
- [ ] Doctor feedback loop → model/agent behavior adaptation
- [ ] A/B testing framework for agent prompt variations

### 7.6 Scalability
- [ ] Docker containerization
- [ ] Kubernetes deployment configs
- [ ] Horizontal scaling for inference (YOLO + CT/MRI)
- [ ] Caching layer for common diagnoses
- [ ] GPU inference support (optional, for speed)

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---|---|---|---|
| Evidence citations | Very High | Low | P0 |
| CPT/ICD-10 codes | High | Low | P0 |
| Red flags checklist | High | Low | P0 |
| Image quality check | High | Low | P0 |
| Streaming responses | High | Medium | P0 |
| Bug fixes | Critical | Low | P0 |
| Tests & CI/CD | High | Medium | P0 |
| **DICOM upload + modality detection** | **High** | **Medium** | **P1** |
| **CT analysis (TotalSegmentator)** | **Very High** | **Medium** | **P1** |
| **MRI knee segmentation** | **High** | **Medium** | **P1** |
| **MRI spine segmentation** | **High** | **Low** | **P1** |
| Follow-up scheduler | High | Low | P1 |
| Second Opinion Agent | High | Medium | P1 |
| Drug Interaction Agent | High | Medium | P1 |
| Surgical Planning Agent | High | High | P1 |
| Automated measurements | High | Medium | P2 |
| Voice dictation | High | Medium | P2 |
| Expanded YOLO models (X-ray) | Medium | High | P2 |
| PACS integration | High | Very High | P2 |
| Template system | Medium | Low | P2 |
| Batch processing | Medium | Medium | P2 |
| RAG pipeline | Medium | Medium | P2 |
| Rehabilitation Agent | Medium | Medium | P2 |
| "Teach Me" mode | Medium | Medium | P3 |
| Insurance/Billing Agent | Medium | Medium | P3 |
| Collaboration features | Medium | High | P3 |
| Case library | Medium | High | P3 |
| Guideline lookup | Medium | Medium | P3 |
| Patient-facing features | Medium | Medium | P3 |
| Risk scoring | High | High | P3 |
| **Custom model training (knee MRI pathology, hospital-specific)** | **Very High** | **Very High** | **P4** |
| Scalability (Docker/K8s) | Medium | High | P3 |

---

## Architecture Notes

### New File Structure (Phase 2 — Multi-Modal)

```
backend/
  tools/
    modality/
      __init__.py              # MODALITY_TOOLS export
      detect_modality.py       # modality_detect_imaging_modality
      dicom_parser.py          # modality_parse_dicom
      dicom_utils.py           # DICOM→NIfTI conversion helpers
    ct/
      __init__.py              # CT_TOOLS export
      ct_runtime.py            # TotalSegmentator + VerSe wrapper
      bone_segmentation.py     # ct_analyze_full_body (117 classes)
      spine_segmentation.py    # ct_analyze_spine (VerSe, C1–S1)
      appendicular_segmentation.py  # ct_analyze_appendicular (foot/hand/knee)
      ct_utils.py              # Segmentation→findings parsing, slice extraction
    mri/
      __init__.py              # MRI_TOOLS export
      mri_runtime.py           # kneeseg + TotalSegmentator MRI wrapper
      knee_segmentation.py     # mri_analyze_knee (bone + cartilage)
      spine_segmentation.py    # mri_analyze_spine (vertebrae on MRI)
      mri_utils.py             # MRI-specific preprocessing
    vision/                    # Existing — no structural changes
      body_part_detector.py    # EDIT: expand body parts
      ...
    __init__.py                # EDIT: merge MODALITY_TOOLS, CT_TOOLS, MRI_TOOLS
```

### Tool Registry Update

```python
# backend/tools/__init__.py
from tools.modality import MODALITY_TOOLS      # 3 tools
from tools.vision import VISION_TOOLS          # 5 tools (existing)
from tools.ct import CT_TOOLS                  # 3 tools
from tools.mri import MRI_TOOLS                # 2 tools
from tools.clinical import CLINICAL_TOOLS      # 5 tools (existing)
from tools.knowledge import KNOWLEDGE_TOOLS    # 5 tools (existing)
from tools.report import REPORT_TOOLS          # 5 tools (existing)
from tools.hospital import HOSPITAL_TOOLS      # 3 tools (existing)

ALL_TOOLS = [
    *MODALITY_TOOLS,
    *VISION_TOOLS,
    *CT_TOOLS,
    *MRI_TOOLS,
    *CLINICAL_TOOLS,
    *KNOWLEDGE_TOOLS,
    *REPORT_TOOLS,
    *HOSPITAL_TOOLS,
]
```

### Data Flow (After Phase 2)

```
Upload (X-ray base64 OR DICOM files)
    │
    ▼
modality_detect_imaging_modality
    │
    ├── "xray" ──→ vision_detect_body_part ──→ detect_hand/leg_fracture ──→ detections
    │                                                                   │
    ├── "ct" ───→ ct_analyze_full_body OR ct_analyze_spine ──→ ct_findings
    │                                              OR ct_analyze_appendicular│
    ├── "mri" ──→ mri_analyze_knee ──→ mri_findings                    │
    │           OR mri_analyze_spine                                     │
    │                                                                   │
    └───────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                    clinical_generate_diagnosis (receives unified findings)
                                        │
                                        ▼
                    clinical_assess_triage → knowledge → report → response
```

### Existing Tools per Agent (unchanged)

| Agent | Tools |
|---|---|
| Modality | `detect_imaging_modality`, `parse_dicom`, `extract_mid_slice` |
| Vision (X-ray) | `detect_body_part`, `detect_hand_fracture`, `detect_leg_fracture`, `annotate_image`, `upload_image` |
| CT | `analyze_full_body`, `analyze_spine`, `analyze_appendicular` |
| MRI | `analyze_knee`, `analyze_spine` |
| Clinical | `generate_diagnosis`, `assess_triage`, `analyze_symptoms`, `multi_study`, `patient_history` |
| Knowledge | `lookup_condition`, `treatment_recommendations`, `anatomy_reference`, `classify_fracture`, `ortho_knowledge` |
| Report | `patient_pdf`, `clinician_pdf`, `clinician_simple_pdf`, `save_report`, `retrieve_report` |
| Hospital | `find_nearby`, `hospital_details`, `emergency_contacts` |
