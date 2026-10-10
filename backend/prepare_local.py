"""Create a local-only template for slow Windows bind-mounted SDK imports."""
from pathlib import Path


def main():
    build=Path(__file__).resolve().parents[1]/'.aws-sam/build'
    # SAM's built template contains ordinary YAML after its transform parsing.
    source=(build/'template.yaml').read_text(encoding='utf-8')
    if source.count('Timeout: 28') != 1:
        raise RuntimeError('Expected the current SAM build with one 28-second function timeout; run sam build first.')
    # Leave deployment timeouts untouched; alter only the generated local copy.
    source=source.replace('Timeout: 28','Timeout: 90')
    (build/'local-template.yaml').write_text(source,encoding='utf-8')
    print('Created .aws-sam/build/local-template.yaml with a 90-second local timeout.')


if __name__=='__main__':
    main()
