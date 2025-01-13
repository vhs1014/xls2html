import pandas as pd
import argparse
from pathlib import Path

async def split_multiline_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame의 각 셀에서 줄바꿈을 발견하면 새로운 행으로 분리하는 함수
    """
    rows_to_split = []
    
    # 모든 행과 열을 순회하면서 줄바꿈이 있는 셀을 찾음
    for idx, row in df.iterrows():
        has_newline = False
        max_lines = 1
        split_data = {}
        
        # 각 열의 값을 확인
        for col in df.columns:
            value = str(row[col])
            if '\n' in value:
                has_newline = True
                lines = value.split('\n')
                max_lines = max(max_lines, len(lines))
                split_data[col] = lines
            else:
                split_data[col] = [value] * max_lines
        
        # 줄바꿈이 있는 경우, 분리된 데이터를 저장
        if has_newline:
            rows_to_split.append((idx, max_lines, split_data))
    
    # 줄바꿈이 있는 행들을 분리하여 새로운 DataFrame 생성
    if rows_to_split:
        new_rows = []
        current_idx = 0
        
        for idx, row in df.iterrows():
            split_info = next((x for x in rows_to_split if x[0] == idx), None)
            
            if split_info:
                _, max_lines, split_data = split_info
                for line_idx in range(max_lines):
                    new_row = {col: split_data[col][line_idx] if line_idx < len(split_data[col]) else ''
                             for col in df.columns}
                    new_rows.append(new_row)
            else:
                new_rows.append(row.to_dict())
            
            current_idx += 1
        
        return pd.DataFrame(new_rows)
    
    return df

def main():
    parser = argparse.ArgumentParser(description='Split multiline cells in Excel file')
    parser.add_argument('input_file', type=str, help='Input Excel file path')
    parser.add_argument('--output_file', type=str, help='Output Excel file path (optional)')
    parser.add_argument('--sheet_name', type=str, default='Sheet1', help='Sheet name to process (default: Sheet1)')
    
    args = parser.parse_args()
    input_path = Path(args.input_file)
    
    # 출력 파일명이 지정되지 않은 경우, 입력 파일명에 '_split' 추가
    if args.output_file:
        output_path = Path(args.output_file)
    else:
        output_path = input_path.parent / f"{input_path.stem}_split{input_path.suffix}"
    
    try:
        # Excel 파일 읽기
        df = pd.read_excel(input_path, sheet_name=args.sheet_name)
        print(f"Successfully read {input_path}")
        
        # 멀티라인 분리
        result_df = split_multiline_rows(df)
        print(f"Processed {len(df)} rows into {len(result_df)} rows")
        
        # 결과 저장
        result_df.to_excel(output_path, index=False, sheet_name=args.sheet_name)
        print(f"Successfully saved to {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())