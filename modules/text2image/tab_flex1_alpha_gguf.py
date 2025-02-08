"""
Copyright NewGenAI
Do not remove this copyright. No derivative code allowed.
"""
import torch
import gradio as gr
import numpy as np
import os
from datetime import datetime
from diffusers import FluxPipeline, FluxTransformer2DModel
from diffusers import GGUFQuantizationConfig
from modules.util.utilities import clear_previous_model_memory
from modules.util import appstate
from modules.util.appstate import state_manager

MAX_SEED = np.iinfo(np.int32).max
OUTPUT_DIR = "output/t2i/Flex.1_alpha"
gguf_list = [
    "Flex.1-alpha-Q3_K_M.gguf - 3.8 GB",
    "Flex.1-alpha-Q3_K_S.gguf - 3.74 GB",
    "Flex.1-alpha-Q4_0.gguf - 4.82 GB",
    "Flex.1-alpha-Q4_K_M.gguf - 4.88 GB",
    "Flex.1-alpha-Q5_0.gguf - 5.83 GB",
    "Flex.1-alpha-Q5_K_M.gguf - 5.89 GB",
    "Flex.1-alpha-Q6_K.gguf - 6.91 GB",
    "Flex.1-alpha-Q8_0.gguf - 8.87 GB"
]

def get_gguf(gguf_user_selection):
    gguf_file, gguf_file_size_str = gguf_user_selection.split(' - ')
    gguf_file_size = float(gguf_file_size_str.replace(' GB', ''))
    return gguf_file, gguf_file_size

def random_seed():
    return torch.randint(0, MAX_SEED, (1,)).item()

def get_pipeline(memory_optimization, gguf_file, vaeslicing, vaetiling):
    model_id = "ostris/Flex.1-alpha"
    dtype = torch.bfloat16
    print("----Flex.1-alpha-GGUF mode: ", memory_optimization, gguf_file, vaeslicing, vaetiling)
    
    if (modules.util.appstate.global_pipe is not None and 
        type(modules.util.appstate.global_pipe).__name__ == "FluxPipeline" and
        modules.util.appstate.global_selected_gguf == gguf_file and
        modules.util.appstate.global_memory_mode == memory_optimization):
        print(">>>>Reusing Flex.1-alpha-GGUF pipe<<<<")
        return modules.util.appstate.global_pipe
    else:
        clear_previous_model_memory()
    
    transformer_path = f"https://huggingface.co/hum-ma/Flex.1-alpha-GGUF/blob/main/{gguf_file}"
    transformer = FluxTransformer2DModel.from_single_file(
        transformer_path,
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=dtype,
        config=model_id,
        subfolder="transformer"
    )

    modules.util.appstate.global_pipe = FluxPipeline.from_pretrained(
        model_id,
        transformer=transformer,
        torch_dtype=dtype,
    )
    
    if memory_optimization == "Low VRAM":
        modules.util.appstate.global_pipe.enable_model_cpu_offload()
    elif memory_optimization == "Extremely Low VRAM":
        modules.util.appstate.global_pipe.enable_model_cpu_offload()

    if vaeslicing:
        modules.util.appstate.global_pipe.vae.enable_slicing()
    else:
        modules.util.appstate.global_pipe.vae.disable_slicing()
    if vaetiling:
        modules.util.appstate.global_pipe.vae.enable_tiling()
    else:
        modules.util.appstate.global_pipe.vae.disable_tiling()

    modules.util.appstate.global_memory_mode = memory_optimization
    modules.util.appstate.global_selected_gguf = gguf_file
    
    return modules.util.appstate.global_pipe

def generate_images(
    seed, prompt, negative_prompt, width, height, guidance_scale,
    num_inference_steps, memory_optimization, vaeslicing, vaetiling, gguf_file
):
    if modules.util.appstate.global_inference_in_progress:
        print(">>>>Inference in progress, can't continue<<<<")
        return None
    
    modules.util.appstate.global_inference_in_progress = True
    try:
        gguf_file, gguf_file_size = get_gguf(gguf_file)
        pipe = get_pipeline(memory_optimization, gguf_file, vaeslicing, vaetiling)
        generator = torch.Generator(device="cpu").manual_seed(seed)

        progress_bar = gr.Progress(track_tqdm=True)

        def callback_on_step_end(pipe, i, t, callback_kwargs):
            progress_bar(i / num_inference_steps, desc=f"Generating image (Step {i}/{num_inference_steps})")
            return callback_kwargs

        inference_params = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "height": height,
            "width": width,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "generator": generator,
            "max_sequence_length": 512,
            "callback_on_step_end": callback_on_step_end,
        }

        image = pipe(**inference_params).images[0]
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}_flex1_alpha.png"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        image.save(output_path)
        print(f"Image generated: {output_path}")
        return [(output_path, "Flex.1-alpha")]
    
    except Exception as e:
        print(f"Error during inference: {str(e)}")
        return None
    finally:
        modules.util.appstate.global_inference_in_progress = False

def create_flex1_alpha_gguf_tab():
    initial_state = state_manager.get_state("flex1_alpha_gguf") or {}

    with gr.Row():
        with gr.Column():
            with gr.Row():
                flex1_alpha_gguf_memory_optimization = gr.Radio(
                    choices=["No optimization", "Low VRAM", "Extremely Low VRAM"],
                    label="Memory Optimization",
                    value=initial_state.get("memory_optimization", "Low VRAM"),
                    interactive=True
                )
            gr.Markdown("### VAE Options")
            with gr.Row():
                flex1_alpha_gguf_vaeslicing = gr.Checkbox(label="VAE Slicing", value=initial_state.get("vaeslicing", True), interactive=True)
                flex1_alpha_gguf_vaetiling = gr.Checkbox(label="VAE Tiling", value=initial_state.get("vaetiling", True), interactive=True)
        with gr.Column():
            with gr.Row():
                flex1_alpha_gguf_dropdown = gr.Dropdown(
                    choices=gguf_list,
                    value=initial_state.get("gguf", "Flex.1-alpha-Q6_K.gguf - 6.91 GB"),
                    label="Select GGUF"
                )
    with gr.Row():
        with gr.Column():
            flex1_alpha_gguf_prompt_input = gr.Textbox(
                label="Prompt", 
                lines=3,
                interactive=True
            )
            flex1_alpha_gguf_negative_prompt_input = gr.Textbox(
                label="Negative Prompt",
                lines=3,
                interactive=True
            )
        with gr.Column():
            with gr.Row():
                flex1_alpha_gguf_width_input = gr.Number(
                    label="Width", 
                    value=initial_state.get("width", 1024),
                    interactive=True
                )
                flex1_alpha_gguf_height_input = gr.Number(
                    label="Height", 
                    value=initial_state.get("height", 1024),
                    interactive=True
                )
                seed_input = gr.Number(label="Seed", value=0, minimum=0, maximum=MAX_SEED, interactive=True)
                random_button = gr.Button("Randomize Seed")
                save_state_button = gr.Button("Save State")
            with gr.Row():
                flex1_alpha_gguf_guidance_scale_slider = gr.Slider(
                    label="Guidance Scale", 
                    minimum=1.0, 
                    maximum=20.0, 
                    value=initial_state.get("guidance_scale", 1.0),
                    step=0.1,
                    interactive=True
                )
                flex1_alpha_gguf_num_inference_steps_input = gr.Number(
                    label="Number of Inference Steps", 
                    value=initial_state.get("inference_steps", 20),
                    interactive=True
                )
    with gr.Row():
        generate_button = gr.Button("Generate image")
    output_gallery = gr.Gallery(
        label="Generated Image(s)",
        columns=3,
        rows=None,
        height="auto"
    )

    def save_current_state(memory_optimization, gguf, vaeslicing, vaetiling, width, height, guidance_scale, inference_steps):
        state_dict = {
            "memory_optimization": memory_optimization,
            "gguf": gguf,
            "vaeslicing": vaeslicing,
            "vaetiling": vaetiling,
            "width": int(width),
            "height": int(height),
            "guidance_scale": guidance_scale,
            "inference_steps": inference_steps
        }
        # print("Saving state:", state_dict)
        initial_state = state_manager.get_state("flex1_alpha_gguf") or {}
        return state_manager.save_state("flex1_alpha_gguf", state_dict)

    # Event handlers
    random_button.click(fn=random_seed, outputs=[seed_input])
    save_state_button.click(
        fn=save_current_state,
        inputs=[
            flex1_alpha_gguf_memory_optimization, 
            flex1_alpha_gguf_dropdown, 
            flex1_alpha_gguf_vaeslicing, 
            flex1_alpha_gguf_vaetiling, 
            flex1_alpha_gguf_width_input, 
            flex1_alpha_gguf_height_input, 
            flex1_alpha_gguf_guidance_scale_slider, 
            flex1_alpha_gguf_num_inference_steps_input
        ],
        outputs=[gr.Textbox(visible=False)]
    )

    generate_button.click(
        fn=generate_images,
        inputs=[
            seed_input, flex1_alpha_gguf_prompt_input, flex1_alpha_gguf_negative_prompt_input, flex1_alpha_gguf_width_input, 
            flex1_alpha_gguf_height_input, flex1_alpha_gguf_guidance_scale_slider, flex1_alpha_gguf_num_inference_steps_input, 
            flex1_alpha_gguf_memory_optimization, flex1_alpha_gguf_vaeslicing, flex1_alpha_gguf_vaetiling, 
            flex1_alpha_gguf_dropdown,
        ],
        outputs=[output_gallery]
    )
