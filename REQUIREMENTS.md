# Environment Requirements

이 프로젝트를 다른 컴퓨터에서 재현하기 위한 환경 설정 가이드입니다.
Node.js 프로젝트는 Python의 `requirements.txt` 대신 `package.json`을 사용하여 의존성을 관리합니다.

## 1. 필수 런타임 (Runtime)
이 프로젝트는 다음 환경에서 개발 및 테스트되었습니다. 호환성을 위해 유사한 버전을 권장합니다.
- **Node.js**: v22.19.0 (LTS 권장, 최소 v18 이상)
- **NPM**: Node.js 설치 시 포함된 버전

## 2. 설치 및 실행 (Installation)

다른 컴퓨터에서 프로젝트를 다운로드(Pull) 받은 후, 다음 명령어를 순서대로 실행하세요.

1. **프로젝트 폴더로 이동**
   ```bash
   cd ortho-photoism
   ```

2. **라이브러리(패키지) 일괄 설치**
   *`package.json`에 명시된 모든 라이브러리를 자동으로 설치합니다.*
   ```bash
   npm install
   ```

3. **개발 서버 실행**
   ```bash
   npm run dev
   ```

## 3. 주요 라이브러리 목록
(상세 버전은 `package.json` 참조)
- **Next.js**: 15+ (App Directory)
- **React**: 19.x
- **Fabric.js**: 6.0.0-beta15
- **Zustand**: 5.x
- **TailwindCSS**: 4.x
- **FileSaver.js**: 2.x
- **jsPDF, JSZip, html2canvas**
