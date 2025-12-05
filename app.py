import streamlit as st
from io import BytesIO
from PIL import Image, ImageDraw
import gc  # Garbage Collector interface

# Try to import pdf2image
try:
    from pdf2image import convert_from_bytes, pdfinfo_from_bytes
except ImportError:
    st.error("Missing required libraries. Please ensure pdf2image and pillow are installed.")
    st.stop()

st.set_page_config(page_title="PDF Label Sheet Generator", layout="wide")

# ============================================================================
# SESSION STATE
# ============================================================================
if 'preview_image' not in st.session_state:
    st.session_state.preview_image = None
if 'file_hash' not in st.session_state:
    st.session_state.file_hash = None
if 'total_pages' not in st.session_state:
    st.session_state.total_pages = 0

# ============================================================================
# 1. FILE UPLOAD & PREVIEW LOADER
# ============================================================================
st.title("🖨️ High-Volume Label Tool")
st.markdown("""
**Optimized for large files.** This tool uses "Batch Processing" to handle files with hundreds of pages without crashing.
""")

uploaded_file = st.file_uploader("Step 1: Upload PDF", type=['pdf'])

if uploaded_file:
    # Reset if new file
    current_hash = hash(uploaded_file.getvalue())
    if st.session_state.file_hash != current_hash:
        st.session_state.preview_image = None
        st.session_state.total_pages = 0
        st.session_state.file_hash = current_hash

    # LOAD PREVIEW BUTTON
    if st.session_state.preview_image is None:
        if st.button("🚀 Load Preview (Instant)"):
            with st.spinner("Reading PDF Metadata..."):
                file_bytes = uploaded_file.read()
                uploaded_file.seek(0)
                
                # Get total page count
                info = pdfinfo_from_bytes(file_bytes)
                st.session_state.total_pages = info["Pages"]
                
                # Load ONLY Page 1 for the UI (Low Res)
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=72)
                st.session_state.preview_image = images[0]
                
            st.rerun()

# ============================================================================
# 2. EDITOR UI
# ============================================================================
if st.session_state.preview_image is not None:
    
    with st.sidebar:
        st.header("⚡ Live Settings")
        
        # Large File Warning
        if st.session_state.total_pages > 100:
            st.warning(f"Large File Detected: {st.session_state.total_pages} pages.\n\nGeneration will happen in batches to prevent crashing.")
        else:
            st.success(f"Loaded: {st.session_state.total_pages} pages.")

        # --- SETTINGS (Same as before) ---
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

        with st.expander("2. Grid & Sheet", expanded=True):
            c1, c2 = st.columns(2)
            sheet_width = c1.number_input("Sheet W", 8.5)
            sheet_height = c2.number_input("Sheet H", 11.0)
            c3, c4 = st.columns(2)
            cols = c3.number_input("Cols", 1, 10, 3)
            rows = c4.number_input("Rows", 1, 20, 4)
            h_spacing = st.slider("Horiz. Gap", 0.0, 1.0, 0.1, 0.05)
            v_spacing = st.slider("Vert. Gap", 0.0, 1.0, 0.1, 0.05)

        with st.expander("3. Margins", expanded=True):
            m_top = st.slider("Top Margin", 0.0, 2.0, 0.5, 0.05)
            c_m1, c_m2 = st.columns(2)
            m_left = c_m1.number_input("Left", 0.0, 2.0, 0.25, 0.05)
            m_right = c_m2.number_input("Right", 0.0, 2.0, 0.25, 0.05)
            m_bot = m_top 

        with st.expander("4. Fine Tuning"):
            show_grid = st.checkbox("Show Red Guidelines", value=True)
            img_scale = st.slider("Scale Image %", 50, 150, 100)
            resize_mode = st.selectbox("Resize Mode", ["fit", "fill", "stretch"])
            start_pos = st.number_input("Start Pos #", 1, 100, 1)

    # --- PREVIEW RENDER ---
    preview_dpi = 72 
    sheet_w_px = int(sheet_width * preview_dpi)
    sheet_h_px = int(sheet_height * preview_dpi)
    mt_px, ml_px = int(m_top * preview_dpi), int(m_left * preview_dpi)
    h_space_px, v_space_px = int(h_spacing * preview_dpi), int(v_spacing * preview_dpi)
    avail_w = sheet_w_px - ml_px - int(m_right * preview_dpi)
    avail_h = sheet_h_px - mt_px - int(m_bot * preview_dpi)

    if use_custom_size:
        final_label_w = int(label_w_input * preview_dpi)
        final_label_h = int(label_h_input * preview_dpi)
    else:
        final_label_w = (avail_w - ((cols - 1) * h_space_px)) // cols
        final_label_h = (avail_h - ((rows - 1) * v_space_px)) // rows

    preview_sheet = Image.new('RGB', (sheet_w_px, sheet_h_px), 'white')
    draw = ImageDraw.Draw(preview_sheet)
    img_preview = st.session_state.preview_image
    
    for pos in range(cols * rows):
        c_idx, r_idx = pos % cols, pos // cols
        x = ml_px + c_idx * (final_label_w + h_space_px)
        y = mt_px + r_idx * (final_label_h + v_space_px)
        
        if show_grid:
            draw.rectangle([x, y, x+final_label_w, y+final_label_h], outline="red", width=2)
        
        visual_pos = pos + 1
        if visual_pos >= start_pos and visual_pos < (start_pos + 1):
            eff_w = int(final_label_w * (img_scale / 100))
            eff_h = int(final_label_h * (img_scale / 100))
            thumb = img_preview.copy()
            thumb.thumbnail((eff_w, eff_h), Image.LANCZOS)
            dest_x = x + (final_label_w - thumb.width) // 2
            dest_y = y + (final_label_h - thumb.height) // 2
            preview_sheet.paste(thumb, (dest_x, dest_y))

    # --- OUTPUT AREA ---
    c_prev, c_info = st.columns([3, 1])
    with c_prev:
        st.subheader("Fast Preview")
        st.image(preview_sheet, use_container_width=True)
    
    with c_info:
        st.info(f"Total Labels: {st.session_state.total_pages}")
        
        # --- BATCH GENERATOR ---
        if st.button("Generate Full PDF", type="primary"):
            
            # Progress UI
            progress_bar = st.progress(0)
            status_box = st.empty() # Placeholder for text updates
            
            # Constants (High Res)
            final_dpi = 300
            f_sheet_w, f_sheet_h = int(sheet_width * final_dpi), int(sheet_height * final_dpi)
            f_mt, f_ml = int(m_top * final_dpi), int(m_left * final_dpi)
            f_hspace, f_vspace = int(h_spacing * final_dpi), int(v_spacing * final_dpi)
            
            f_avail_w = f_sheet_w - f_ml - int(m_right * final_dpi)
            f_avail_h = f_sheet_h - f_mt - int(m_bot * final_dpi)
            
            if use_custom_size:
                f_lbl_w = int(label_w_input * final_dpi)
                f_lbl_h = int(label_h_input * final_dpi)
            else:
                f_lbl_w = (f_avail_w - ((cols - 1) * f_hspace)) // cols
                f_lbl_h = (f_avail_h - ((rows - 1) * f_vspace)) // rows

            # Logic
            output_sheets = []
            labels_per_sheet = cols * rows
            total_items = st.session_state.total_pages + (start_pos - 1)
            total_out_sheets = (total_items + labels_per_sheet - 1) // labels_per_sheet
            
            # Batching
            BATCH_SIZE = 50 
            grid_position = 0
            label_read_head = 0 
            current_sheet = Image.new('RGB', (f_sheet_w, f_sheet_h), 'white')
            
            file_bytes = uploaded_file.getvalue() 

            # Loop through file in chunks
            while label_read_head < st.session_state.total_pages:
                
                # UI Update
                batch_end = min(label_read_head + BATCH_SIZE, st.session_state.total_pages)
                status_box.markdown(f"""
                **Processing Batch...**
                * Labels: {label_read_head+1} to {batch_end}
                * Progress: {int((label_read_head / st.session_state.total_pages) * 100)}%
                * *Please wait...*
                """)
                
                # Load Batch
                batch_images = convert_from_bytes(
                    file_bytes, 
                    first_page=label_read_head+1, 
                    last_page=batch_end, 
                    dpi=final_dpi
                )
                
                # Place Batch
                for img in batch_images:
                    while grid_position < (start_pos - 1):
                        if (grid_position + 1) % labels_per_sheet == 0:
                            output_sheets.append(current_sheet)
                            current_sheet = Image.new('RGB', (f_sheet_w, f_sheet_h), 'white')
                        grid_position += 1
                    
                    pos_on_sheet = grid_position % labels_per_sheet
                    c_idx = pos_on_sheet % cols
                    r_idx = pos_on_sheet // cols
                    
                    x = f_ml + c_idx * (f_lbl_w + f_hspace)
                    y = f_mt + r_idx * (f_lbl_h + f_vspace)
                    
                    # Resize
                    orig_w, orig_h = img.size
                    eff_w = int(f_lbl_w * (img_scale / 100))
                    eff_h = int(f_lbl_h * (img_scale / 100))
                    
                    if resize_mode == "stretch":
                        resized = img.resize((eff_w, eff_h), Image.LANCZOS)
                    elif resize_mode == "fill":
                        ratio = max(eff_w/orig_w, eff_h/orig_h)
                        nw, nh = int(orig_w*ratio), int(orig_h*ratio)
                        resized = img.resize((nw, nh), Image.LANCZOS)
                        l, t = (nw-eff_w)//2, (nh-eff_h)//2
                        resized = resized.crop((l, t, l+eff_w, t+eff_h))
                    else:
                        ratio = min(eff_w/orig_w, eff_h/orig_h)
                        nw, nh = int(orig_w*ratio), int(orig_h*ratio)
                        resized = img.resize((nw, nh), Image.LANCZOS)
                        bg = Image.new('RGB', (eff_w, eff_h), 'white')
                        bg.paste(resized, ((eff_w-nw)//2, (eff_h-nh)//2))
                        resized = bg
                    
                    # Center Paste
                    dest_x = x + (f_lbl_w - resized.width) // 2
                    dest_y = y + (f_lbl_h - resized.height) // 2
                    current_sheet.paste(resized, (dest_x, dest_y))
                    
                    grid_position += 1
                    
                    if (pos_on_sheet + 1) == labels_per_sheet:
                        output_sheets.append(current_sheet)
                        current_sheet = Image.new('RGB', (f_sheet_w, f_sheet_h), 'white')
                        progress_bar.progress(min(len(output_sheets) / total_out_sheets, 0.99))

                label_read_head = batch_end
                
                # CRITICAL MEMORY CLEANUP
                del batch_images
                gc.collect() # Force RAM release
            
            # Final Sheet
            if (grid_position % labels_per_sheet) != 0:
                output_sheets.append(current_sheet)
                
            progress_bar.progress(1.0)
            status_box.success("✅ Done! Compiling PDF...")
            
            pdf_buffer = BytesIO()
            output_sheets[0].save(pdf_buffer, "PDF", resolution=final_dpi, save_all=True, append_images=output_sheets[1:])
            
            st.download_button("⬇️ Download Final PDF", pdf_buffer.getvalue(), "labels.pdf", "application/pdf")
