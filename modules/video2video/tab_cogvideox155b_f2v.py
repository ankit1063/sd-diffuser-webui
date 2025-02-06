"""
Copyright NewGenAI
Do not remove this copyright. No derivative code allowed.
"""
import torch
import gradio as gr
import numpy as np
import os
import modules.util.appstate
from datetime import datetime
from diffusers.utils import export_to_video, load_video
from diffusers import CogVideoXFunControlPipeline, DDIMScheduler
from modules.util.utilities import clear_previous_model_memory

MAX_SEED = np.iinfo(np.int32).max
OUTPUT_DIR = "output/v2v/cogvideox155b"

def random_seed():
    return torch.randint(0, MAX_SEED, (1,)).item()

def get_pipeline(memory_optimization, vaeslicing, vaetiling):
    print("----CogVideoXFunControlPipeline mode: ", memory_optimization, vaeslicing, vaetiling)
    # If model is already loaded with same configuration, reuse it
    if (modules.util.appstate.global_pipe is not None and 
        type(modules.util.appstate.global_pipe).__name__ == "CogVideoXFunControlPipeline" and
        modules.util.appstate.global_memory_mode == memory_optimization):
        print(">>>>Reusing CogVideoXFunControlPipeline pipe<<<<")
        return modules.util.appstate.global_pipe
    else:
        clear_previous_model_memory()
    
    modules.util.appstate.global_pipe = CogVideoXFunControlPipeline.from_pretrained(
        "alibaba-pai/CogVideoX-Fun-V1.1-5b-Pose",
        torch_dtype=torch.bfloat16
    )

    if memory_optimization == "Low VRAM":
        modules.util.appstate.global_pipe.enable_model_cpu_offload()
    elif memory_optimization == "Extremely Low VRAM":
        modules.util.appstate.global_pipe.enable_sequential_cpu_offload()

    if vaeslicing:
        modules.util.appstate.global_pipe.vae.enable_slicing()
    else:
        modules.util.appstate.global_pipe.vae.disable_slicing()
    if vaetiling:
        modules.util.appstate.global_pipe.vae.enable_tiling()
    else:
        modules.util.appstate.global_pipe.vae.disable_tiling()

    modules.util.appstate.global_memory_mode = memory_optimization
    
    return modules.util.appstate.global_pipe
def process_video_input(video_path):
    """Convert video input to the format expected by the pipeline"""
    try:
        # Use diffusers' load_video function to properly load the video
        video_frames = load_video(video_path)
        return video_frames
    except Exception as e:
        raise ValueError(f"Error processing video: {str(e)}")

def generate_video(
    input_video, guidance_scale, seed, prompt, negative_prompt, width, height, fps,
    num_inference_steps, use_dynamic_cfg, memory_optimization, vaeslicing, vaetiling
):
    if modules.util.appstate.global_inference_in_progress == True:
        print(">>>>Inference in progress, can't continue<<<<")
        return None
    modules.util.appstate.global_inference_in_progress = True
    try:
        # Get pipeline (either cached or newly loaded)
        pipe = get_pipeline(memory_optimization, vaeslicing, vaetiling)
        generator = torch.Generator(device="cuda").manual_seed(seed)
        progress_bar = gr.Progress(track_tqdm=True)

        def callback_on_step_end(pipe, i, t, callback_kwargs):
            progress_bar(i / num_inference_steps, desc=f"Generating video (Step {i}/{num_inference_steps})")
            return callback_kwargs
        processed_video = process_video_input(input_video)
        # Prepare inference parameters
        inference_params = {
            "control_video": processed_video,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "height": height,
            "width": width,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "generator": generator,
            "use_dynamic_cfg": use_dynamic_cfg,
            "callback_on_step_end": callback_on_step_end,
        }

        # Generate video
        video = pipe(**inference_params).frames[0]
        
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        base_filename = "cogvideox155bf2v.mp4"
        
        gallery_items = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}_{base_filename}"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        # Save the video
        export_to_video(video, output_path, fps=fps)
        print(f"Video generated: {output_path}")
        modules.util.appstate.global_inference_in_progress = False
        
        return output_path
    except Exception as e:
        print(f"Error during inference: {str(e)}")
        return None
    finally:
        modules.util.appstate.global_inference_in_progress = False

def create_cogvideox155b_f2v_tab():
    with gr.Row():
        with gr.Column():
            cogvideox155bf2v_memory_optimization = gr.Radio(
                choices=["No optimization", "Low VRAM", "Extremely Low VRAM"],
                label="Memory Optimization",
                value="Extremely Low VRAM",
                interactive=True
            )
        with gr.Column():
            cogvideox155bf2v_vaeslicing = gr.Checkbox(label="VAE slicing", value=True, interactive=True)
            cogvideox155bf2v_vaetiling = gr.Checkbox(label="VAE Tiling", value=True, interactive=True)
    with gr.Row():
        with gr.Column():
            cogvideox155bf2v_input_video = gr.Video(label="Input Video")
            cogvideox155bf2v_prompt_input = gr.Textbox(
                label="Prompt", 
                lines=5,
                interactive=True
            )
            cogvideox155bf2v_negative_prompt_input = gr.Textbox(
                label="Negative Prompt",
                lines=3,
                interactive=True
            )
        with gr.Column():
            with gr.Row():
                cogvideox155bf2v_width_input = gr.Number(
                    label="Width", 
                    value=512, 
                    interactive=True
                )
                cogvideox155bf2v_height_input = gr.Number(
                    label="Height", 
                    value=320, 
                    interactive=True
                )
                seed_input = gr.Number(label="Seed", value=0, minimum=0, maximum=MAX_SEED, interactive=True)
                random_button = gr.Button("Randomize Seed")
            with gr.Row():
                cogvideox155bf2v_fps_input = gr.Number(
                    label="FPS", 
                    value=15,
                    interactive=True
                )
                cogvideox155bf2v_num_inference_steps_input = gr.Number(
                    label="Number of Inference Steps", 
                    value=50,
                    interactive=True
                )
                cogvideox155bf2v_use_dynamic_cfg = gr.Checkbox(label="Use Dynamic CFG", value=True)
                cogvideox155bf2v_guidance_scale = gr.Slider(label="Guidance Scale", minimum=1, maximum=20, step=0.1, value=6)
    with gr.Row():
        generate_button = gr.Button("Generate video")
    output_video = gr.Video(label="Generated Video", show_label=True)

    # Event handlers
    random_button.click(fn=random_seed, outputs=[seed_input])

    generate_button.click(
        fn=generate_video,
        inputs=[
            cogvideox155bf2v_input_video, cogvideox155bf2v_guidance_scale,
            seed_input, cogvideox155bf2v_prompt_input, cogvideox155bf2v_negative_prompt_input, 
            cogvideox155bf2v_width_input, cogvideox155bf2v_height_input, cogvideox155bf2v_fps_input, 
            cogvideox155bf2v_num_inference_steps_input,  
            cogvideox155bf2v_use_dynamic_cfg, cogvideox155bf2v_memory_optimization, 
            cogvideox155bf2v_vaeslicing, cogvideox155bf2v_vaetiling
        ],
        outputs=[output_video]
    )