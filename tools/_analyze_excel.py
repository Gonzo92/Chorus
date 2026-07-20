import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_excel(r'D:\LOGI\2026\APR\106_MCD_Ulysses_Exynos9975-EVT0 FC_260430.xlsx', sheet_name='Sheet1')

print('=== ALL TEST CASES WITH KEY PARAMS ===')
for idx, row in df.iterrows():
    print(str(idx) + ': ' + str(row['TR Name']))
    print('   Level8: ' + str(row['Level8']))
    print('   Level10: ' + str(row['Level10']))
    print('   Band: ' + str(row['Band Combination']))
    print('   SIM: ' + str(row['Tested SIM']))
    print('   Carriers: ' + str(row['Level6']))
    print('   Total: ' + str(row['[DUT,REF] Total']))
    print('   DUT Result: ' + str(row['[DUT] Result']))
    print('   REF Result: ' + str(row['[REF1] Result']))
    print('   SCG Fail DUT: ' + str(row['[DUT] SCG failure']))
    print('   SCG Fail REF: ' + str(row['[REF1] SCG failure']))
    print()
