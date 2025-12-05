import streamlit as st
import sys
from io import BytesIO
from PIL import Image

# Try to import pdf2image, warn if missing
try:
    from pdf2image import convert_from_bytes
except ImportError:
    st.error("Missing required libraries. Please run: pip install pdf2image pillow")
    st.stop()
except Exception as e:
    st.error(f"Error importing pdf2image. Make sure Poppler is installed. Error: {e}")
    st.stop()

# ============================================================================
# UI CONFIGURATION
# ============================================================================
st.set_page_config(page_title="PDF Label Sheet Generator", layout="wide")

st.title("📄 PDF to Label Sheet Converter")
st.markdown("""
Upload a PDF containing individual label pages, and this tool will arrange them 
onto a grid for printing (e.g., Avery sheets).
""")

# ============================================================================
# SIDEBAR SETTINGS
# ============================================================================
with st.sidebar:
    st.header("⚙️ Sheet Configuration")
    
    # 1. Sheet Dimensions
    st.subheader("Paper Size (Inches)")
    col1, col2 = st.columns(2)
    with col1:
        sheet_width = st.number_input("Sheet Width", value=8.0, step=0.5)
    with col2:
        sheet_height = st.number_input("Sheet Height", value=12.0, step=0.5)

    # 2. Grid Configuration
    st.subheader("Grid Layout")
    col3, col4 = st.columns(2)
    with col3:
        cols = st.number_input("Columns", min_value=1, value=3)
    with col4:
        rows = st.number_input("Rows", min_value=1, value=4)

    # 3. Label Dimensions (The "Auto" Logic)
    st.subheader("Label Dimensions")
    use_custom_size = st.checkbox("Use specific label size?", value=False, 
                                  help="If unchecked, labels will auto-size to fill the grid.")
    
    label_w, label_h = None, None
    h_spacing, v_spacing = 0.0, 0.0

    if use_custom_size:
        c1, c2 = st.columns(2)
        with c1:
            label_w = st.number_input("Label Width (in)", value=3.5, step=0.1)
        with c2:
            label_h = st.number_input("Label Height (in)", value=2.5, step=0.1)
        
        st.caption("Spacing between labels")
        c3, c4 = st.columns(2)
        with c3:
            h_spacing = st.number_input("Horiz. Spacing", value=0.25, step=0.05)
        with c4:
            v_spacing = st.number_input("Vert. Spacing", value=0.25, step=0.05)

    # 4. Margins & Buffers
    with st.expander("Margins & Padding (Advanced)"):
        st.write("Sheet Edges (inches)")
        m_top = st.number_input("Top Margin", value=0.1, step=0.05)
        m_bot = st.number_input("Bottom Margin", value=0.1, step=0.05)
        m_left = st.number_input("Left Margin", value=0.1, step=0.05)
        m_right = st.number_input("Right Margin", value=0.1, step=0.05)
        
        st.write("Inner Label Padding")
        label_buffer = st.number_input("Safety Buffer", value=0.1, step=0.05, 
                                       help="White space added inside the label to prevent cut-off.")

    # 5. Image Processing Options
    st.subheader("Processing Options")
    resize_mode = st.selectbox(
        "Resize Mode", 
        options=["fit", "fill", "stretch"],
        index=0,
        help="Fit: Adds whitespace. Fill: Crops edges to fill. Stretch: Distorts image."
    )
    dpi = st.number_input("DPI (Resolution)", value=300, step=50)


# ============================================================================
# MAIN LOGIC
# ============================================================================

uploaded_file = st.file_uploader("Drag and drop your PDF here", type=['pdf'])

if uploaded_file is not None:
    if st.button("Generate Label Sheet"):
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            status_text.text("Reading PDF...")
            # Convert uploaded file (bytes) to images directly in memory
            # We use fmt='jpeg' to speed up processing for the preview, but stick to internal PIL for final
            pages = convert_from_bytes(uploaded_file.read(), dpi=dpi)
            
            if not pages:
                st.error("No pages found in the PDF.")
                st.stop()

            # --- CALCULATIONS (Ported from your script) ---
            sheet_width_px = int(sheet_width * dpi)
            sheet_height_px = int(sheet_height * dpi)
            
            # Margins
            edge_margin_top_px = int(m_top * dpi)
            edge_margin_left_px = int(m_left * dpi)
            label_buffer_px = int(label_buffer * dpi)
            
            # Available space
            available_width_px = sheet_width_px - int(m_left * dpi) - int(m_right * dpi)
            available_height_px = sheet_height_px - int(m_top * dpi) - int(m_bot * dpi)
            
            # Determine Label Size
            if use_custom_size:
                label_width_px = int(label_w * dpi)
                label_height_px = int(label_h * dpi)
                h_spacing_px = int(h_spacing * dpi)
                v_spacing_px = int(v_spacing * dpi)
            else:
                label_width_px = available_width_px // cols
                label_height_px = available_height_px // rows
                h_spacing_px = 0
                v_spacing_px = 0

            # Content area
            content_width_px = label_width_px - (2 * label_buffer_px)
            content_height_px = label_height_px - (2 * label_buffer_px)

            # --- GENERATION ---
            output_sheets = []
            total_labels = len(pages)
            labels_per_sheet = cols * rows
            num_sheets = (total_labels + labels_per_sheet - 1) // labels_per_sheet

            status_text.text(f"Processing {total_labels} labels into {num_sheets} sheets...")

            for sheet_num in range(num_sheets):
                # Update Progress
                progress = (sheet_num) / num_sheets
                progress_bar.progress(progress)
                
                # Create blank sheet
                sheet = Image.new('RGB', (sheet_width_px, sheet_height_px), 'white')
                
                for pos in range(labels_per_sheet):
                    label_idx = sheet_num * labels_per_sheet + pos
                    if label_idx >= total_labels:
                        break
                    
                    # Process Image
                    label_img = pages[label_idx]
                    orig_w, orig_h = label_img.size
                    
                    # RESIZE LOGIC
                    if resize_mode == "stretch":
                        resized = label_img.resize((content_width_px, content_height_px), Image.LANCZOS)
                    elif resize_mode == "fill":
                        ratio = max(content_width_px / orig_w, content_height_px / orig_h)
                        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
                        resized = label_img.resize((new_w, new_h), Image.LANCZOS)
                        left = (new_w - content_width_px) // 2
                        top = (new_h - content_height_px) // 2
                        resized = resized.crop((left, top, left + content_width_px, top + content_height_px))
                    else: # fit
                        ratio = min(content_width_px / orig_w, content_height_px / orig_h)
                        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
                        resized = label_img.resize((new_w, new_h), Image.LANCZOS)
                        centered = Image.new('RGB', (content_width_px, content_height_px), 'white')
                        paste_x = (content_width_px - new_w) // 2
                        paste_y = (content_height_px - new_h) // 2
                        centered.paste(resized, (paste_x, paste_y))
                        resized = centered
                    
                    # Apply Buffer
                    if label_buffer_px > 0:
                        buffered = Image.new('RGB', (label_width_px, label_height_px), 'white')
                        buffered.paste(resized, (label_buffer_px, label_buffer_px))
                        resized = buffered
                    
                    # Calculate Position
                    col = pos % cols
                    row = pos // cols
                    
                    if use_custom_size:
                        x = edge_margin_left_px + col * (label_width_px + h_spacing_px)
                        y = edge_margin_top_px + row * (label_height_px + v_spacing_px)
                    else:
                        x = edge_margin_left_px + col * label_width_px
                        y = edge_margin_top_px + row * label_height_px
                    
                    sheet.paste(resized, (x, y))
                
                output_sheets.append(sheet)

            progress_bar.progress(1.0)
            status_text.text("Done!")

            # --- PREVIEW ---
            st.subheader("Preview (First Sheet)")
            st.image(output_sheets[0], caption=f"Sheet 1 of {len(output_sheets)}", use_container_width=True)

            # --- DOWNLOAD ---
            # Save to memory buffer
            pdf_buffer = BytesIO()
            output_sheets[0].save(
                pdf_buffer, "PDF", resolution=dpi, save_all=True, 
                append_images=output_sheets[1:] if len(output_sheets) > 1 else []
            )
            
            st.download_button(
                label="⬇️ Download Processed PDF",
                data=pdf_buffer.getvalue(),
                file_name="processed_labels.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.info("Tip: If you are on a Mac, make sure you ran `brew install poppler`")