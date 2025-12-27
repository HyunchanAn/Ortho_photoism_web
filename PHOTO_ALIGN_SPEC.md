# 기획 문서: 교정용 포토 얼라인(PhotoAlign) - Local Ultimate Spec

이 문서는 `PhotoAlign`의 전체 가이드(15+ 페이지)를 완벽하게 분석하여, **로컬 웹 환경**에서 원본 소프트웨어의 기능을 100% 구현하는 것을 목표로 합니다.

## 1. 프로젝트 개요 (Project Overview)
- **Target**: 교정 치과 의료진 (High-End Users).
- **Goal**: "설치 없는 웹 기반 PhotoAlign". 강력한 커스텀 템플릿, 자동화된 배치, 정밀한 보정.
- **Key UX**: **Template-Driven Workflow** (모든 것은 템플릿 설정에 따름).

## 2. 상세 기능 명세 (Detailed Specifications)

### 2.1 템플릿 엔진 (Custom Template Engine)
가이드의 `canvas.xml` 구조를 JSON 기반 설정으로 변환하여 구현합니다.
- **Structure**: `Template > Board > Canvas[]` & `Extras > Guideline[]`.
- **Canvas Attributes**:
  - `id`: 고유 ID.
  - `geometry`: `left`, `top`, `width`, `height` (상대 좌표 % 기준).
  - `meta`: `title`, `description`.
  - **`automation`**:
    - `preload`: 자동 배치를 위한 파일명 키워드 리스트 (예: `['front', 'f.jpg']`).
    - `savename`: 저장 시 사용할 예약 파일명 (예: `frontal_smile`).
    - `order`: 파일 순서 기반 배치를 위한 인덱스.
  - **`preAction`**:
    - `rotation`: 기본 회전각 (예: 구내 사진 180도 회전).
    - `flip`: `horizontal` | `vertical`.
    - `magnification`: 초기 확대 비율 (50~200%).

### 2.2 자동 배치 시스템 (Allocation System)
- **AI Allocation (Filename Based)**:
  - 업로드된 파일명 ↔ 템플릿 `preload` 키워드 매칭.
  - 매칭 성공 시 해당 슬롯으로 자동 이동 및 `preAction` 적용.
- **File Order Allocation**:
  - 파일 리스트 순서(1, 2, 3..)대로 템플릿 `order` 속성 슬롯에 순차 배치.

### 2.3 편집 및 보정 (Photo Manipulation & Actions)
- **Canvas Toolbar**:
  - `Reset`: 이미지 제거.
  - `Revert`: 원본 상태로 복구 (편집 취소).
  - `Reset Position`: 위치/회전만 초기화 (필터 유지).
- **One-click Actions (Filters)**:
  - **Normalize / Auto Level**: 히스토그램 스트레칭.
  - **Denoise**: 블러 기반 노이즈 제거.
  - **Enlight / Envivid**: 밝기/채도 부스트 Presets.
  - **Grayscale**: 흑백 변환 (Rec. 709).
- **Simultaneous Editing**: 다중 선택된 캔버스에 동일 조작 적용.

### 2.4 출력 및 리네이머 (Export & Renamer)
- **Preview Save Window**:
  - 저장 전 미리보기 및 파일명 일괄 변경.
- **Renamer Logic**:
  - 변수 조합: `<Original Name>`, `<Reserved Name>(savename)`, `<Folder Name>`, `<Index>`, `<Date>`.
  - 예: `[<Folder Name>]_<Reserved Name>_<Index>.jpg`.
- **Save Options**:
  - **Merged Image**: 전체 캔버스 병합 저장.
  - **Save Each Photo**: 개별 슬롯 이미지를 리네이밍 규칙에 따라 다중 다운로드 (Zip or Multiple Blobs).
  - **Print/PDF**: A4/Letter 레이아웃 매핑 및 PDF 생성.

## 3. 기술 설계 (Technical Design)

### 3.1 Tech Stack (Fixed)
- **Core**: Next.js 14 (App Router), React, TypeScript.
- **UI**: TailwindCSS (Dark Theme), Lucide Icons, Shadcn/UI (Optional for complex forms).
- **Canvas**: **Fabric.js v6**.
- **State**: Zustand (Store).
- **Imaging**: 
  - `Fabric.Image.filters` (Brightness, Contrast, Grayscale).
  - Custom WebGL filters for 'Auto Level' (Histogram analysis required).

### 3.2 Data Model (Zustand Store)
```typescript
type CanvasConfig = {
  id: string; // "canvas-1"
  templateId: string; // "ortho-basic"
  preAction: { rotate: number; flip: 'h'|'v'|null; scale: number };
  keywords: string[]; // ["front", "smile"]
  savename: string; // "frontal"
  // ... geometry
};

interface EditorState {
  activeTemplate: TemplateDefinition;
  canvases: Record<string, FabricObject>; // fabric instances
  assets: FileAsset[]; // Uploaded raw files
  // ... actions
}
```

## 4. 구현 단계 (Phase Plan)

### Phase 1: Template Engine & Core
- [ ] **Template Loader**: JSON 설정 파일(`ortho_basic.json`)을 읽어 동적으로 캔버스 그리드 생성.
- [ ] **Drag & Drop Manager**: 파일 업로드 시 `preload` 키워드 분석하여 슬롯 자동 할당.
- [ ] **Pre-action Processor**: 이미지 로드 시 `rotation`, `flip` 속성 자동 적용.

### Phase 2: Manipulation & Tools
- [ ] **Fabric Canvas Toolbar**: 각 슬롯 별 Reset/Revert/ResetPos 버튼 오버레이.
- [ ] **One-click Filter Pipeline**: Normalize, Grayscale, Brightness 필터 구현.
- [ ] **Multi-select System**: Shift+Click 지원 및 일괄 속성 변경.

### Phase 3: Advanced Features (Guides & Props)
- [ ] **Advanced Guides**: XML 기반 가이드라인(`attach` to canvas) 렌더링.
- [ ] **Edit Canvas Properties**: 템플릿 속성(키워드, 예약명) 런타임 수정 모달.

### Phase 4: Export Suite
- [ ] **Renamer UI**: `<Tag>` 방식의 파일명 생성기 구현.
- [ ] **Batch Saver**: `JSZip`을 이용해 개별 이미지/병합 이미지 일괄 다운로드.
- [ ] **PDF Generator**: `jspdf`로 출력 레이아웃 렌더링.

## 5. 검증 (Verification)
- **Scenario 1 (Auto Alloc)**: `front.jpg` 파일을 드롭했을 때, `keywords: ['front']`인 캔버스에 180도 회전(Pre-action)되어 들어가는가?
- **Scenario 2 (Renamer)**: `<Reserved Name>_<Index>` 규칙 적용 시 `frontal_01.jpg`로 저장되는가?
- **Scenario 3 (Filters)**: 'Grayscale' 클릭 시 9개 사진 중 선택된 3개만 흑백으로 변하되, 위치는 유지되는가?
