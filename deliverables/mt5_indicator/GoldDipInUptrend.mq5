//+------------------------------------------------------------------+
//| GoldDipInUptrend.mq5 - Agent City                                |
//| SIGNALS ONLY. This indicator never opens, modifies or closes     |
//| trades. Not financial advice.                                    |
//| Status: candidate in Agent City's live forward test since        |
//| 2026-11-05. NOT proven profitable yet. The validation period was |
//| seen in earlier research runs, so only new days count.           |
//+------------------------------------------------------------------+
#property copyright   "Agent City"
#property version     "1.00"
#property description "Buy pullbacks inside a long-term uptrend (signals only)."
#property indicator_chart_window
#property indicator_buffers 3
#property indicator_plots   2
#property indicator_label1  "BUY"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrDeepSkyBlue
#property indicator_width1  2
#property indicator_label2  "SELL"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrOrangeRed
#property indicator_width2  2

input int    InpTrend   = 100;   // Uptrend SMA period (T)
input double InpDip     = 0.03;  // Pullback from 20-bar high close (x, 0.03 = 3%)
input int    InpExitMA  = 20;    // Rebound exit SMA period (E)
input bool   InpAlerts  = true;  // Popup alert on a new signal
input bool   InpPush    = false; // Push notification to the MT5 mobile app

double BuyBuf[];
double SellBuf[];
double PosBuf[];                 // 1 = in position, 0 = flat (state per bar)
datetime g_lastAlert = 0;

int OnInit()
  {
   if(InpTrend < 2 || InpExitMA < 2 || InpDip <= 0.0 || InpDip >= 0.5)
      return(INIT_PARAMETERS_INCORRECT);
   SetIndexBuffer(0, BuyBuf,  INDICATOR_DATA);
   SetIndexBuffer(1, SellBuf, INDICATOR_DATA);
   SetIndexBuffer(2, PosBuf,  INDICATOR_CALCULATIONS);
   ArraySetAsSeries(BuyBuf, false);
   ArraySetAsSeries(SellBuf, false);
   ArraySetAsSeries(PosBuf, false);
   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME, StringFormat("GoldDipInUptrend(%d,%.2f,%d)", InpTrend, InpDip, InpExitMA));
   return(INIT_SUCCEEDED);
  }

double Sma(const double &c[], int i, int n)
  {
   double s = 0.0;
   for(int k = i - n + 1; k <= i; k++)
      s += c[k];
   return(s / n);
  }

double MaxClose(const double &c[], int i, int n)
  {
   double m = c[i];
   for(int k = i - n + 1; k <= i; k++)
      if(c[k] > m) m = c[k];
   return(m);
  }

int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
  {
   ArraySetAsSeries(time, false);
   ArraySetAsSeries(high, false);
   ArraySetAsSeries(low, false);
   ArraySetAsSeries(close, false);
   if(rates_total < 3)
      return(0);
   int last = rates_total - 2;                         // last CLOSED bar (the forming bar never signals)
   int start = (prev_calculated > 1) ? prev_calculated - 2 : 0;
   if(start < 0) start = 0;
   for(int i = start; i <= last; i++)
     {
      double prev = (i > 0) ? PosBuf[i - 1] : 0.0;
      double cur = prev;
      BuyBuf[i]  = EMPTY_VALUE;
      SellBuf[i] = EMPTY_VALUE;
      if(i >= 19 && i >= InpExitMA - 1)                // warm-up: 20-bar high and exit SMA must exist
        {
         bool trend = (i >= InpTrend - 1) && (close[i] > Sma(close, i, InpTrend));
         double hi20 = MaxClose(close, i, 20);
         double exitMa = Sma(close, i, InpExitMA);
         if(prev == 0.0 && trend && close[i] <= hi20 * (1.0 - InpDip))
            cur = 1.0;
         else if(prev == 1.0 && ((close[i] > exitMa && close[i] > close[i - 1]) || !trend))
            cur = 0.0;
        }
      PosBuf[i] = cur;
      double pad = (high[i] - low[i]) * 0.4;
      if(cur == 1.0 && prev == 0.0) BuyBuf[i]  = low[i]  - pad;
      if(cur == 0.0 && prev == 1.0) SellBuf[i] = high[i] + pad;
     }
   BuyBuf[rates_total - 1] = EMPTY_VALUE;
   SellBuf[rates_total - 1] = EMPTY_VALUE;
   PosBuf[rates_total - 1] = PosBuf[last];
   // one alert per new closed-bar signal, never for history
   if(prev_calculated > 0 && time[last] != g_lastAlert && (BuyBuf[last] != EMPTY_VALUE || SellBuf[last] != EMPTY_VALUE))
     {
      g_lastAlert = time[last];
      string msg = StringFormat("%s %s: %s signal (GoldDipInUptrend, signals only)", _Symbol,
                                EnumToString((ENUM_TIMEFRAMES)_Period), BuyBuf[last] != EMPTY_VALUE ? "BUY" : "SELL");
      if(InpAlerts) Alert(msg);
      if(InpPush) SendNotification(msg);
     }
   return(rates_total);
  }
//+------------------------------------------------------------------+
