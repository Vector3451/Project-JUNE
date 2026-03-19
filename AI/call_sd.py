import argparse
import torch
import os
from diffusers import StableDiffusionXLPipeline

parser = argparse.ArgumentParser()
parser.add_argument("--prompt", type=str, required=True)
parser.add_argument("--output", type=str, required=True)
parser.add_argument("--width", type=int, default=1024)
parser.add_argument("--height", type=int, default=1024)
args = parser.parse_args()

model_path = r"D:\Programs\StabilityMatrix-win-x64\Data\Packages\reforge\models\Stable-diffusion\NoobAI-XL-v1.1.safetensors"

if not os.path.exists(model_path):
    print(f"Error: Model not found at {model_path}")
    exit(1)

# Load as SDXL
pipe = StableDiffusionXLPipeline.from_single_file(
    model_path,
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True
).to("cuda")


# Optimization
pipe.enable_model_cpu_offload()

image = pipe(
    args.prompt, 
    width=args.width, 
    height=args.height, 
    num_inference_steps=30, 
    guidance_scale=7.0
).images[0]

image.save(args.output)
print("Image saved! :", args.output)

