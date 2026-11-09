# 2010년 확장 검증 자료

이 디렉터리는 기존 연구에서 사용한 입력과 비교 장부를 압축해 보관한다.
다른 폴더나 네트워크 없이 저장소 루트에서 다음을 실행한다.

```sh
python tools/research_2010_close_execution.py
```

필요 라이브러리는 저장소의 requirements.txt를 따른다. 출력은
`release/long-close-2010/`에 생성된다. 실행기는 2014년과 2024년
잘라낸 입력의 신호 일치, 당일 가격 반영 순서, 별도 금액 장부의 일치,
실제 BITO 구간의 기존 장부 일치를 검사한다.

- reconstructed_inputs.csv.gz: 기존 신호용 혼합 가격 기준을 보존한
  2010년 이후 입력과 2026년 11월 4일까지의 방어자산 연장분.
- nav_actual_BITO_next_open.csv.gz: 실제 BITO 구간에서 기존 장부와의
  일치를 확인하는 비교값.
- 나머지 BTC와 주식 입력, 실제 BITO 가격은 각각 data/btc.csv,
  data/equities.csv 및 data/validation/v2/inputs_actual_BITO.npz를 사용한다.

2010년 장부의 BITO는 2011년부터 BTC에 연간 추적 오차 가정을 적용한
대용값이며 실제 ETF 운용 실적이 아니다. 주식 가격 기준은 혼합되어 있고
세금·환율·부분체결은 반영하지 않는다. 2026년 사례를 본 뒤 규칙을
선택한 연구이므로 독립 미래 검증이 아니다. 당일 확정 종가를 확인한 후
같은 가격에 거래한다는 결과는 가상의 가격 참조다.
