import streamlit as st
from io import BytesIO
from PIL import Image, ImageDraw

# Try to import pdf2image
try:
    from pdf2image import convert_from_bytes
except ImportError:
    st.error("Missing required libraries. Please ensure pdf2image and pillow are installed.")
    st.stop()

st.set_page_config(page_title="PDF Label Sheet Generator", layout="wide")

# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================
# This keeps the images in memory so we don't have to reload the PDF 
# every time you move a margin slider.
if 'images' not in st.session_state:
    st.session_state.images = None
if 'file_hash' not in st.session_state:
    st.session_state.file_hash = None

# ============================================================================
# 1. FILE UPLOAD SECTION
# ============================================================================
st.title("🖨️ Live Label Editor")
st.markdown("Upload a PDF, then tweak margins and sizing in real-time.")

uploaded_file = st.file_uploader("Step 1: Upload PDF", type=['pdf'])

if uploaded_file:
    # Check if this is a new file (to clear old cache)
    current_hash = hash(uploaded_file.getvalue())
    if st.session_state.file_hash != current_hash:
        st.session_state.images = None
        st.session_state.file_hash = current_hash

    # Show "Load" button only if we haven't processed the images yet
    if st.session_state.images is None:
        if st.button("🚀 Load Images & Start Editing"):
            with st.spinner("Converting PDF to images (One time)..."):
                # 300 DPI is standard for print quality
                st.session_state.images = convert_from_bytes(uploaded_file.read(), dpi=300)
            st.rerun() # Refresh page to show the editor
    
# ============================================================================
# 2. THE LIVE EDITOR (Only shows if images are loaded)
# ============================================================================
if st.session_state.images is not None:
    
    # --- SIDEBAR CONTROLS (Live) ---
    with st.sidebar:
        st.header("⚡ Live Settings")
        st.info("Adjust these sliders to see changes instantly.")

        # A. SIZING MODE
        with st.expander("1. Layout Strategy", expanded=True):
            sizing_mode = st.radio("Mode", ["Auto-Fill Grid", "Specific Size"], label_visibility="collapsed")
            
            if sizing_mode == "Specific Size":
                c_size1, c_size2 = st.columns(2)
                label_w_input = c_size1.number_input("Width (in)", value=3.5, step=0.1)
                label_h_input = c_size2.number_input("Height (in)", value=2.0, step=0.1)
                use_custom_size = True
            else:
                use_custom_size = False
                label_w_input, label_h_input = None, None

        # B. GRID & SHEET
        with st.expander("2. Grid & Sheet", expanded=True):
            c1, c2 = st.columns(2)
            sheet_width = c1.number_input("Sheet W", 8.5)
            sheet_height = c2.number_input("Sheet H", 11.0)
            
            c3, c4 = st.columns(2)
            cols = c3.number_input("Cols", 1, 10, 3)
            rows = c4.number_input("Rows", 1, 20, 4)
            
            st.caption("Spacing")
            h_spacing = st.slider("Horiz. Gap", 0.0, 1.0, 0.1, 0.05)
            v_spacing = st.slider("Vert. Gap", 0.0, 1.0, 0.1, 0.05)

        # C. MARGINS (Using Sliders for "Live" feel)
        with st.expander("3. Margins", expanded=True):
            m_top = st.slider("Top Margin", 0.0, 2.0, 0.5, 0.05)
            c_m1, c_m2 = st.columns(2)
            m_left = c_m1.number_input("Left", 0.0, 2.0, 0.25, 0.05)
            m_right = c_m2.number_input("Right", 0.0, 2.0, 0.25, 0.05)
            # Bottom margin usually matters less, keeping it simple
            m_bot = m_top 

        # D. FINE TUNING
        with st.expander("4. Fine Tuning"):
            show_grid = st.checkbox("Show Red Guidelines", value=True)
            img_scale = st.slider("Scale Image %", 50, 150, 100)
            resize_mode = st.selectbox("Resize Mode", ["fit", "fill", "stretch"])
            start_pos = st.number_input("Start Pos #", 1, 100, 1)

    # ========================================================================
    # 3. LIVE RENDER LOGIC
    # ========================================================================
    
    # --- MATH (Runs instantly on every slider move) ---
    dpi = 300
    sheet_w_px = int(sheet_width * dpi)
    sheet_h_px = int(sheet_height * dpi)
    
    mt_px, mb_px = int(m_top * dpi), int(m_bot * dpi)
    ml_px, mr_px = int(m_left * dpi), int(m_right * dpi)
    h_space_px, v_space_px = int(h_spacing * dpi), int(v_spacing * dpi)
    
    available_w = sheet_w_px - ml_px - mr_px
    available_h = sheet_h_px - mt_px - mb_px

    if use_custom_size:
        final_label_w = int(label_w_input * dpi)
        final_label_h = int(label_h_input * dpi)
    else:
        total_h_gaps = (cols - 1) * h_space_px
        total_v_gaps = (rows - 1) * v_space_px
        final_label_w = (available_w - total_h_gaps) // cols
        final_label_h = (available_h - total_v_gaps) // rows
    
    # --- DRAWING SHEET 1 (PREVIEW) ---
    # We only draw Sheet 1 here for speed. 
    # Full PDF generation happens only when they click "Download".
    
    preview_sheet = Image.new('RGB', (sheet_w_px, sheet_h_px), 'white')
    draw = ImageDraw.Draw(preview_sheet)
    
    pages = st.session_state.images
    labels_per_sheet = cols * rows
    
    # Limit loop to 1 sheet or total labels
    loop_range = min(labels_per_sheet, len(pages) + (start_pos - 1))
    
    curr_page_idx = 0
    
    for pos in range(loop_range):
        # Grid Math
        col_idx = pos % cols
        row_idx = pos // cols
        x = ml_px + col_idx * (final_label_w + h_space_px)
        y = mt_px + row_idx * (final_label_h + v_space_px)
        
        # Guide Lines
        if show_grid:
            draw.rectangle([x, y, x + final_label_w, y + final_label_h], outline="red", width=5)
            
        # Skip Logic
        if pos < (start_pos - 1): continue
        if curr_page_idx >= len(pages): break
        
        img = pages[curr_page_idx]
        curr_page_idx += 1
        
        # Resize Logic
        orig_w, orig_h = img.size
        # Apply manual scale slider
        effective_w = int(final_label_w * (img_scale / 100))
        effective_h = int(final_label_h * (img_scale / 100))
        
        if resize_mode == "stretch":
            resized = img.resize((effective_w, effective_h), Image.LANCZOS)
        elif resize_mode == "fill":
            ratio = max(effective_w/orig_w, effective_h/orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - effective_w) // 2
            top = (new_h - effective_h) // 2
            resized = resized.crop((left, top, left + effective_w, top + effective_h))
        else: # fit
            ratio = min(effective_w/orig_w, effective_h/orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            bg = Image.new('RGB', (effective_w, effective_h), 'white')
            paste_x = (effective_w - new_w) // 2
            paste_y = (effective_h - new_h) // 2
            bg.paste(resized, (paste_x, paste_y))
            resized = bg
            
        # Paste Centered in Slot
        dest_x = x + (final_label_w - resized.width) // 2
        dest_y = y + (final_label_h - resized.height) // 2
        
        preview_sheet.paste(resized, (dest_x, dest_y))

    # --- DISPLAY ---
    col_prev, col_stats = st.columns([3, 1])
    
    with col_prev:
        st.subheader("Live Preview (Sheet 1)")
        st.image(preview_sheet, use_container_width=True, caption="Red lines will NOT be printed if unchecked in sidebar.")

    with col_stats:
        st.subheader("Summary")
        st.write(f"**Total Labels:** {len(pages)}")
        st.write(f"**Grid:** {cols}x{rows} ({labels_per_sheet}/page)")
        total_sheets = (len(pages) + (start_pos - 1) + labels_per_sheet - 1) // labels_per_sheet
        st.write(f"**Total Sheets:** {total_sheets}")
        
        if show_grid:
            st.warning("⚠️ Grid lines are ON")
        
        st.write("---")
        st.write("Ready to print?")
        
        # --- FINAL GENERATION BUTTON ---
        # This is the only part that takes time, to generate ALL pages
        if st.button("Download Full PDF", type="primary"):
            
            # (Here we replicate the loop for ALL sheets, not just the preview)
            full_sheets = []
            final_progress = st.progress(0)
            
            curr_full_idx = 0
            for s_idx in range(total_sheets):
                sheet = Image.new('RGB', (sheet_w_px, sheet_h_px), 'white')
                # No red lines on final print
                
                for p in range(labels_per_sheet):
                    a_pos = s_idx * labels_per_sheet + p
                    
                    if a_pos < (start_pos - 1): continue
                    if curr_full_idx >= len(pages): break
                    
                    # ... (Re-use resize logic briefly for final render) ...
                    # For brevity, reusing the exact same logic as above
                    img_f = pages[curr_full_idx]
                    curr_full_idx += 1
                    
                    orig_w, orig_h = img_f.size
                    eff_w = int(final_label_w * (img_scale / 100))
                    eff_h = int(final_label_h * (img_scale / 100))
                    
                    if resize_mode == "fill":
                        r = max(eff_w/orig_w, eff_h/orig_h)
                        nw, nh = int(orig_w*r), int(orig_h*r)
                        res = img_f.resize((nw, nh), Image.LANCZOS)
                        l = (nw-eff_w)//2
                        t = (nh-eff_h)//2
                        res = res.crop((l, t, l+eff_w, t+eff_h))
                    elif resize_mode == "stretch":
                        res = img_f.resize((eff_w, eff_h), Image.LANCZOS)
                    else:
                        r = min(eff_w/orig_w, eff_h/orig_h)
                        nw, nh = int(orig_w*r), int(orig_h*r)
                        res = img_f.resize((nw, nh), Image.LANCZOS)
                        bg = Image.new('RGB', (eff_w, eff_h), 'white')
                        bg.paste(res, ((eff_w-nw)//2, (eff_h-nh)//2))
                        res = bg
                        
                    # Calculate X/Y
                    c_i = p % cols
                    r_i = p // cols
                    fx = ml_px + c_i * (final_label_w + h_space_px)
                    fy = mt_px + r_i * (final_label_h + v_space_px)
                    
                    dx = fx + (final_label_w - res.width) // 2
                    dy = fy + (final_label_h - res.height) // 2
                    sheet.paste(res, (dx, dy))
                
                full_sheets.append(sheet)
                final_progress.progress((s_idx + 1) / total_sheets)
            
            # Save
            pdf_buffer = BytesIO()
            full_sheets[0].save(pdf_buffer, "PDF", resolution=dpi, save_all=True, append_images=full_sheets[1:])
            
            st.download_button(
                label="⬇️ Click to Save PDF",
                data=pdf_buffer.getvalue(),
                file_name="final_labels.pdf",
                mime="application/pdf"
            )
