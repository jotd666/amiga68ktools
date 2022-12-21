use clap::Parser;

mod lvos;

use lvos::lvos::Lvo;
   	
/// Simple program to greet a person
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
   /// Name of the person to greet
   #[arg(short, long)]
   input_file: String,

   /// Number of times to greet
   #[arg(short, long, default_value_t = String::from(""))]
   output_file: String,
}

fn main() {
   let args = Args::parse();

   /*    println!("Hello {}!", args.input_file);
       println!("Hello {}!", args.output_file);*/
   
   let lvo = Lvo::new();
}