"""User-requested supplement: recorded returns after residential third paid service."""
from datetime import datetime, timezone
import json

from scripts import benchmark_warranty_models as b
from scripts import research_callback_targets as research


def main():
    output = b.ROOT/'outputs/model_validation/20261016_target_research_3x'
    protocol_path = b.ROOT/'config/cp2_3x_final_target_research_20261017.json'
    if protocol_path.exists() or output.exists():
        raise ValueError('Preserve supplement evidence; do not overwrite')
    protocol = json.loads(research.PROTOCOL.read_text(encoding='utf-8'))
    original = b.ROOT/protocol['inputs']['features']['path']
    if research.digest(original) != protocol['inputs']['features']['sha256']:
        raise ValueError('Original source changed')
    source = b.load_dataset_input(original)
    subset = source[source.premise_type.eq('RESIDENTIAL')
                    & source.package_sessions_recorded.eq(3)].copy()
    output.mkdir(parents=True)
    b.persist_dataset_input(subset, output)
    protocol['declared_at_utc'] = datetime.now(timezone.utc).isoformat()
    protocol['user_requested_supplement'] = 'Residential 3x programmes after actual third paid service; Calendar return/warranty signals, not formal claim sheet submissions'
    protocol['original_full_source'] = protocol['inputs']['features']
    protocol['inputs']['features'] = {'path':str((output/'dataset_input.json').relative_to(b.ROOT)).replace('\\','/'),
                                     'sha256':research.digest(output/'dataset_input.json')}
    protocol['targets'] = ['final_paid_service']
    protocol['populations'] = ['residential']
    protocol['code_sha256'] = research.digest(research.__file__)
    protocol['supplement_runner_sha256'] = research.digest(__file__)
    protocol['limits'].append('30-day horizon matches the stated 3x claim period; other horizons are sensitivity analyses, not changed warranty entitlement.')
    research.write(protocol_path,protocol)
    print(f'Declared residential 3x supplement from {len(subset)} source service windows',flush=True)
    research.OUT = output
    research.PROTOCOL = protocol_path
    research.main()


if __name__=='__main__':
    main()
