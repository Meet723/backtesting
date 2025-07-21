import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import warnings
warnings.filterwarnings('ignore')

# Set page config
st.set_page_config(
    page_title="Trading Strategy Analyzer", 
    page_icon="📈", 
    layout="wide"
)

# Title and description
st.title("📈 Trading Strategy Analyzer")
st.markdown("Upload your Excel file to analyze trading performance with customizable targets and stop-loss levels")

# Sidebar for controls
st.sidebar.header("Strategy Parameters")

# Target and Stop Loss inputs
target_pct = st.sidebar.number_input(
    "Target Percentage (%)", 
    min_value=0.1, 
    max_value=50.0, 
    value=3.0, 
    step=0.1,
    help="Set your profit target percentage"
)

sl_pct = st.sidebar.number_input(
    "Stop Loss Percentage (%)", 
    min_value=0.1, 
    max_value=50.0, 
    value=2.0, 
    step=0.1,
    help="Set your stop loss percentage"
)

# Function to get stock price data
@st.cache_data
def get_stock_price(symbol, date):
    """Fetch stock price for a given symbol and date"""
    try:
        # Add .NS for NSE stocks if not already present
        if not symbol.endswith('.NS'):
            symbol_formatted = f"{symbol}.NS"
        else:
            symbol_formatted = symbol
            
        # Convert date string to datetime
        if isinstance(date, str):
            try:
                # Handle different date formats
                if '/' in date:
                    date = datetime.strptime(date, '%d/%m/%Y')
                elif '-' in date:
                    date = datetime.strptime(date, '%d-%m-%Y')
            except:
                # Try alternative formats
                try:
                    date = datetime.strptime(date, '%m/%d/%Y')
                except:
                    date = datetime.strptime(date, '%Y-%m-%d')
        
        # Get data for a week around the date to handle weekends/holidays
        start_date = date - timedelta(days=7)
        end_date = date + timedelta(days=7)
        
        # Fetch data
        ticker = yf.Ticker(symbol_formatted)
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            return None
            
        # Find the closest trading day
        target_date = date.strftime('%Y-%m-%d')
        if target_date in data.index.strftime('%Y-%m-%d'):
            return data.loc[data.index.strftime('%Y-%m-%d') == target_date, 'Close'].iloc[0]
        else:
            # Get the closest available date
            data['date_diff'] = abs((data.index.date - date.date()).days)
            closest_idx = data['date_diff'].idxmin()
            return data.loc[closest_idx, 'Close']
            
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

# Function to determine which hit first
def check_target_or_sl_first(symbol, entry_date, entry_price, target_price, sl_price):
    """Check whether target or stop loss was hit first"""
    try:
        # Add .NS for NSE stocks
        if not symbol.endswith('.NS'):
            symbol_formatted = f"{symbol}.NS"
        else:
            symbol_formatted = symbol
            
        # Convert date if string
        if isinstance(entry_date, str):
            try:
                if '/' in entry_date:
                    entry_date = datetime.strptime(entry_date, '%d/%m/%Y')
                elif '-' in entry_date:
                    entry_date = datetime.strptime(entry_date, '%d-%m-%Y')
            except:
                try:
                    entry_date = datetime.strptime(entry_date, '%m/%d/%Y')
                except:
                    entry_date = datetime.strptime(entry_date, '%Y-%m-%d')
        
        # Get data for next 30 days
        start_date = entry_date
        end_date = entry_date + timedelta(days=30)
        
        ticker = yf.Ticker(symbol_formatted)
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            return "No Data"
        
        # Check each day after entry
        for idx, row in data.iterrows():
            if idx.date() > entry_date.date():  # Skip entry date
                high = row['High']
                low = row['Low']
                
                # Check if target hit (assuming long position)
                if high >= target_price:
                    return "Target Hit"
                
                # Check if stop loss hit
                if low <= sl_price:
                    return "Stop Loss Hit"
        
        # If neither hit within 30 days
        return "Neither Hit"
        
    except Exception as e:
        return f"Error: {str(e)}"

# Main app
def main():
    # File upload
    st.header("📁 Upload Your Excel File")
    uploaded_file = st.file_uploader(
        "Choose an Excel file", 
        type=['xlsx', 'xls'],
        help="Upload Excel file with columns: date, symbol, marketcapname, sector"
    )
    
    if uploaded_file is not None:
        try:
            # Read the uploaded file
            df = pd.read_excel(uploaded_file)
            
            # Display original data
            st.subheader("📊 Original Data")
            st.dataframe(df.head(10))
            
            # Check if required columns exist
            required_columns = ['date', 'symbol', 'marketcapname', 'sector']
            if not all(col in df.columns for col in required_columns):
                st.error(f"Missing required columns. Required: {required_columns}")
                st.stop()
            
            # Process data
            with st.spinner('Fetching stock prices... This may take a while.'):
                
                # Initialize new columns
                df['close_price'] = 0.0
                df['target_pct'] = target_pct
                df['sl_pct'] = sl_pct
                df['result'] = 'Processing...'
                
                # Create progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Process each row
                for idx, row in df.iterrows():
                    progress = (idx + 1) / len(df)
                    progress_bar.progress(progress)
                    status_text.text(f'Processing {idx + 1}/{len(df)}: {row["symbol"]}')
                    
                    # Get stock price
                    close_price = get_stock_price(row['symbol'], row['date'])
                    
                    if close_price is not None:
                        df.at[idx, 'close_price'] = round(close_price, 2)
                        
                        # Calculate target and stop loss prices
                        target_price = close_price * (1 + target_pct / 100)
                        sl_price = close_price * (1 - sl_pct / 100)
                        
                        # Check which was hit first
                        result = check_target_or_sl_first(
                            row['symbol'], 
                            row['date'], 
                            close_price, 
                            target_price, 
                            sl_price
                        )
                        df.at[idx, 'result'] = result
                    else:
                        df.at[idx, 'close_price'] = 0.0
                        df.at[idx, 'result'] = 'Price Not Found'
                
                progress_bar.empty()
                status_text.empty()
            
            # Display processed data
            st.subheader("📈 Processed Data with Results")
            
            # Rename columns for better display
            display_df = df.copy()
            display_df.columns = ['Date', 'Symbol', 'Market Cap', 'Sector', 'Close Price', 'Target %', 'SL %', 'Result']
            
            st.dataframe(display_df, use_container_width=True)
            
            # Create analysis section
            st.subheader("📊 Strategy Analysis")
            
            # Calculate statistics
            col1, col2, col3, col4 = st.columns(4)
            
            total_trades = len(df)
            target_hit = len(df[df['result'] == 'Target Hit'])
            sl_hit = len(df[df['result'] == 'Stop Loss Hit'])
            no_result = len(df[df['result'].isin(['Neither Hit', 'No Data', 'Price Not Found'])])
            
            with col1:
                st.metric("Total Trades", total_trades)
            
            with col2:
                st.metric("Target Hit", target_hit, f"{(target_hit/total_trades*100):.1f}%")
            
            with col3:
                st.metric("Stop Loss Hit", sl_hit, f"{(sl_hit/total_trades*100):.1f}%")
                
            with col4:
                st.metric("No Result", no_result, f"{(no_result/total_trades*100):.1f}%")
            
            # Create visualizations
            col1, col2 = st.columns(2)
            
            with col1:
                # Pie chart of results
                result_counts = df['result'].value_counts()
                fig_pie = px.pie(
                    values=result_counts.values, 
                    names=result_counts.index,
                    title="Trade Results Distribution"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Sector-wise performance
                sector_results = df.groupby(['sector', 'result']).size().reset_index(name='count')
                fig_bar = px.bar(
                    sector_results, 
                    x='sector', 
                    y='count', 
                    color='result',
                    title="Sector-wise Performance"
                )
                fig_bar.update_xaxes(tickangle=45)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Market cap analysis
            st.subheader("📈 Market Cap Analysis")
            marketcap_results = df.groupby(['marketcapname', 'result']).size().reset_index(name='count')
            fig_marketcap = px.bar(
                marketcap_results, 
                x='marketcapname', 
                y='count', 
                color='result',
                title="Market Cap wise Performance"
            )
            st.plotly_chart(fig_marketcap, use_container_width=True)
            
            # Time series analysis
            st.subheader("📅 Time Series Analysis")
            df['date'] = pd.to_datetime(df['date'], format='mixed')
            df['month'] = df['date'].dt.to_period('M')
            monthly_results = df.groupby(['month', 'result']).size().reset_index(name='count')
            
            fig_timeline = px.line(
                monthly_results, 
                x='month', 
                y='count', 
                color='result',
                title="Monthly Performance Trend"
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
            
            # P&L Calculation
            st.subheader("💰 Profit & Loss Analysis")
            
            df['pnl_pct'] = 0.0
            df.loc[df['result'] == 'Target Hit', 'pnl_pct'] = target_pct
            df.loc[df['result'] == 'Stop Loss Hit', 'pnl_pct'] = -sl_pct
            
            total_pnl = df['pnl_pct'].sum()
            win_rate = (target_hit / (target_hit + sl_hit) * 100) if (target_hit + sl_hit) > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total P&L %", f"{total_pnl:.2f}%")
            
            with col2:
                st.metric("Win Rate", f"{win_rate:.1f}%")
                
            with col3:
                avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
                st.metric("Average P&L per Trade", f"{avg_pnl:.2f}%")
            
            # Download processed file
            st.subheader("💾 Download Processed Data")
            
            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                display_df.to_excel(writer, sheet_name='Processed_Data', index=False)
            
            st.download_button(
                label="📥 Download Excel File",
                data=output.getvalue(),
                file_name=f"processed_strategy_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.error("Please make sure your Excel file has the correct format with columns: date, symbol, marketcapname, sector")

if __name__ == "__main__":
    main()