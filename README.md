# Ortho Photoism (PhotoAlign Clone)

**Ortho Photoism**은 치과교정용 사진(Intraoral/Extraoral)을 손쉽게 정렬하고 편집할 수 있는 웹 기반 로컬 애플리케이션입니다. `photoalign.com`의 핵심 기능을 벤치마킹하여, 직관적인 UI와 강력한 편집 기능을 제공합니다.

## 주요 기능 (Features)

### 1. 템플릿 엔진 & 스마트 업로더
- **자동 할당**: 파일명에 포함된 키워드(`upper`, `smile`, `rest` 등)를 분석하여 적절한 슬롯에 자동 배치합니다.
- **Drag & Drop**: 폴더나 파일을 브라우저로 드래그하여 즉시 편집을 시작할 수 있습니다.
- **복합 레이아웃 (Composite Layout)**:
    - **구외(Face)**: 상단에 3:4 비율로 가로 배열 (Rest, Profile 45°, Profile 90°, Smile)
    - **구내(Intraoral)**: 하단에 4:3 비율로 십자(Cross) 배열 (Upper, Right, Center, Left, Lower)

### 2. 강력한 편집 도구 (Manipulation)
- **이동 및 크기 조절**: 마우스 드래그와 휠을 이용한 직관적인 Pan & Zoom.
- **회전(Rotation)**: 
    - **슬라이더 회전**: 각 슬롯 툴바의 슬라이더(R)를 통해 -180° ~ +180° 정밀 회전 (블록 중심 기준).
- **미러링(Mirror)**: `Flip Horizontal` 버튼을 통해 좌우 반전(거울상) 처리 가능.
- **이미지 보정**: 밝기(Brightness), 대비(Contrast) 조절 및 `Normalize`, `Grayscale` 원클릭 필터.
- **다중 편집**: 여러 슬롯을 체크박스로 선택하여 한 번에 일괄 조정 가능.

### 3. 내보내기 (Export)
- **일괄 저장 (ZIP)**: 편집된 모든 이미지를 고해상도 JPG로 변환하여 ZIP 압축 다운로드 (`FileSaver.js` 적용).
- **PDF 리포트**: A4 가로 규격에 맞춘 PDF 출력 기능.
- **스마트 리네이머**: `[<Savename>]_<Index>` 패턴을 이용한 파일명 일괄 변경 지원.

## 🛠 기술 스택 (Tech Stack)
- **Framework**: [Next.js 15+](https://nextjs.org/) (App Directory)
- **Language**: TypeScript
- **Canvas Engine**: [Fabric.js v6 (Beta)](http://fabricjs.com/)
- **State Management**: [Zustand](https://github.com/pmndrs/zustand)
- **Styling**: [TailwindCSS](https://tailwindcss.com/)
- **Export Libs**: `jspdf`, `jszip`, `file-saver`, `html2canvas`

## 설치 및 실행 (Installation)

이 프로젝트는 `ortho-photoism` 하위 디렉토리에 구성되어 있습니다.

### 1. 프로젝트 클론 및 의존성 설치
```bash
# 프로젝트 폴더로 이동
cd ortho-photoism

# 의존성 패키지 설치
npm install
```

### 2. 개발 서버 실행
```bash
npm run dev
```
실행 후 브라우저에서 `http://localhost:3000`으로 접속하세요.

### 3. 빌드 (Production Build)
```bash
npm run build
npm start
```

## 프로젝트 구조 (Structure)
```
ortho-photoism/
├── src/
│   ├── app/                # Next.js App Router
│   ├── components/
│   │   ├── editor/         # 캔버스 및 편집 관련 컴포넌트 (EditorLayout, PhotoSlot 등)
│   │   └── ui/             # 공통 UI 컴포넌트
│   ├── data/               # 템플릿 정의 (orthodontic_basic.ts)
│   ├── store/              # 전역 상태 관리 (editorStore.ts)
│   └── types/              # 타입 정의
└── public/                 # 정적 리소스 (참조 이미지 등)
```

## 라이선스 (License)
This project is for educational/personal use.
