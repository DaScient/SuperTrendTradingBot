{"metadata":{"kernelspec":{"language":"python","display_name":"Python 3","name":"python3"},"language_info":{"name":"python","version":"3.10.12","mimetype":"text/x-python","codemirror_mode":{"name":"ipython","version":3},"pygments_lexer":"ipython3","nbconvert_exporter":"python","file_extension":".py"},"kaggle":{"accelerator":"none","dataSources":[],"dockerImageVersionId":30822,"isInternetEnabled":true,"language":"python","sourceType":"notebook","isGpuEnabled":false}},"nbformat_minor":4,"nbformat":4,"cells":[{"source":"<a href=\"https://www.kaggle.com/code/dascient/donutz-ai-tier-1?scriptVersionId=215703986\" target=\"_blank\"><img align=\"left\" alt=\"Kaggle\" title=\"Open in Kaggle\" src=\"https://kaggle.com/static/images/open-in-kaggle.svg\"></a>","metadata":{},"cell_type":"markdown"},{"cell_type":"code","source":"from IPython.display import clear_output\n!pip install pandas_ta\n!pip install schedule\n!pip install config\n!pip install pykalman\nclear_output()\nimport schedule,warnings,time,ast,config\nfrom pykalman import KalmanFilter\nfrom dateutil.tz import tzlocal\nfrom datetime import datetime\nfrom random import randint\nfrom random import seed\nimport pandas_ta as ta\nimport pandas as pd\nimport numpy as np\nimport smtplib\nwarnings.filterwarnings('ignore')\ndf = pd.read_csv('https://www.cryptodatadownload.com/cdd/Binance_SHIBUSDT_1h.csv',header=1)\nCARRIERS = {\"att\": \"@mms.att.net\",\n    \"tmobile\": \"@tmomail.net\",\n    \"verizon\": \"@vtext.com\",\n    \"sprint\": \"@messaging.sprintpcs.com\"}\nEMAIL = \"aristocles24@gmail.com\"\nPASSWORD = \"odxx ontt dgbz nabo\"","metadata":{"trusted":true,"execution":{"iopub.status.busy":"2025-01-01T19:32:49.404255Z","iopub.execute_input":"2025-01-01T19:32:49.404599Z","iopub.status.idle":"2025-01-01T19:33:05.809719Z","shell.execute_reply.started":"2025-01-01T19:32:49.404571Z","shell.execute_reply":"2025-01-01T19:33:05.808604Z"}},"outputs":[],"execution_count":14},{"cell_type":"code","source":"def send_message(phone_number, carrier, message):\n    recipient = phone_number + CARRIERS[carrier]\n    auth = (EMAIL, PASSWORD)\n    server = smtplib.SMTP(\"smtp.gmail.com\", 587)\n    server.starttls()\n    server.login(auth[0], auth[1])\n    server.sendmail(auth[0], recipient, message)\ndef supertrend(df):\n    df['close'] = df['Close']\n    df['low'] = df['Low']\n    df['high'] = df['High']\n    df['open'] = df['Open']\n    close = df['close'][len(df)-1]\n    low = df['low'][len(df)-1]\n    kf = KalmanFilter(transition_matrices = [1],    # The value for At. It is a random walk so is set to 1.0\n                      observation_matrices = [1],   # The value for Ht.\n                      initial_state_mean = 0,       # Any initial value. It will converge to the true state value.\n                      initial_state_covariance = 1, # Sigma value for the Qt in Equation (1) the Gaussian distribution\n                      observation_covariance=1,     # Sigma value for the Rt in Equation (2) the Gaussian distribution\n                      transition_covariance=.01)    # A small turbulence in the random walk parameter 1.0\n    state_means, _ = kf.filter(df['close'].values)\n    df['kf_mean'] = np.array(state_means)\n    kalman = df.kf_mean[len(df)-1]\n    aboveKalman = low > kalman\n    ema_13 = df.ta.ema(13, append=True)[-1:].reset_index(drop=True)[0]\n    ema_31 = df.ta.ema(31, append=True)[-1:].reset_index(drop=True)[0]\n    ema_crossover  = ema_13 > kalman\n    bbl_14 = df.ta.bbands(length=14, append=True)[['BBL_14_2.0']].tail(1).values[0][0]\n    bbu_14 = df.ta.bbands(length=14, append=True)[['BBU_14_2.0']].tail(1).values[0][0]\n    bband_buy = close < bbl_14\n    bband_sell = close > bbu_14\n    isa_9 = df.ta.ichimoku()[1]['ISA_9'].tail(1).values[0] # help(ta.ichimoku)\n    isb_26 = df.ta.ichimoku()[1]['ISB_26'].tail(1).values[0]\n    amat = (df.ta.amat()['AMATe_LR_8_21_2'].tail(1).values[0] == 1)\n    rsi = df.ta.rsi()[len(df)-1]\n    rsi_buy = rsi < 30\n    rsi_sell = rsi > 70\n    try: \n        chop = \"{:.2f}\".format(df.ta.chop()[len(df.ta.chop())-1]) \n    except RunTimeWarning:\n        chop = 0\n    buy = ema_13 > kalman\n    sell = ema_13 < kalman\n    return df, close, isa_9, isb_26, chop, rsi, amat, ema_crossover, buy, sell, aboveKalman\n    #.      0,      1,     2,      3,    4,   5,    6,             7,   8,     9,          10\ndef plot(df,symbol):\n    fig = go.Figure(go.Candlestick(x=df.index,open=df['open'],high=df['high'],low=df['low'],close=df['close'],name=symbol))\n    fig.add_trace(go.Scatter(x=df.index,y=df['kf_mean'],opacity=0.7,line=dict(color='purple', width=2),name='Kalman Filter'))\n    fig.add_trace(go.Scatter(x=df.index,y=df['EMA_13'],opacity=0.7,line=dict(color='orange', width=2),name='EMA_13'))\n    fig.add_trace(go.Scatter(x=df.index,y=df['EMA_31'],opacity=0.7,line=dict(color='lightblue', width=2),name='EMA_31 '))\n    fig.update_layout(title=f'Ticker: {symbol}')\n    fig.update_layout(xaxis_rangeslider_visible=False)\n    return fig.show()","metadata":{"trusted":true,"execution":{"iopub.status.busy":"2025-01-01T19:37:26.581517Z","iopub.execute_input":"2025-01-01T19:37:26.581892Z","iopub.status.idle":"2025-01-01T19:37:26.596295Z","shell.execute_reply.started":"2025-01-01T19:37:26.581859Z","shell.execute_reply":"2025-01-01T19:37:26.59525Z"}},"outputs":[],"execution_count":21},{"cell_type":"code","source":"def run_bot():                    \n    supertrend(df)\n    df_enhanced = df\n    if df_enhanced[8]:\n        supertrend(\"3016750611\", \"tmobile\", f\"buy shib\")\n    if df_enhanced[9]:\n        supertrend(\"3016750611\", \"tmobile\", f\"sell shib\")\nschedule.every(9).seconds.do(run_bot)\nwhile True:\n    schedule.run_pending()\n    time.sleep(0)","metadata":{"_uuid":"8f2839f25d086af736a60e9eeb907d3b93b6e0e5","_cell_guid":"b1076dfc-b9ad-4769-8c92-a6c4dae69d19","trusted":true,"execution":{"iopub.status.busy":"2025-01-01T19:37:31.070053Z","iopub.execute_input":"2025-01-01T19:37:31.070393Z"}},"outputs":[],"execution_count":null},{"cell_type":"code","source":"#en fin","metadata":{"trusted":true},"outputs":[],"execution_count":null}]}